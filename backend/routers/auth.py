"""
Login, OTP and MFA status.

Password login and email OTP go through the API so they can be rate limited and so repeated
failed logins lock the account for LOGIN_LOCKOUT_MINUTES. The session Supabase returns is
handed back for the frontend to set. Failure counters are in memory (per process), which
is enough for the prototype; production would keep them in a shared store.
"""
import logging
import time
from typing import Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.config import settings
from core.ratelimit import rate_limit
from core.security import AuthenticatedUser, MFA_ROLES, get_current_user, mfa_satisfied

logger = logging.getLogger("proofpath.auth")
router = APIRouter(prefix="/auth", tags=["Auth"])

_failures: Dict[str, List[float]] = {}
EMAIL = Field(..., max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginRequest(BaseModel):
    email: str = EMAIL
    password: str = Field(..., min_length=1, max_length=200)


class OtpRequest(BaseModel):
    email: str = EMAIL


class OtpVerify(BaseModel):
    email: str = EMAIL
    token: str = Field(..., pattern=r"^\d{6}$")


def _locked_for(email: str) -> int:
    """Seconds until the account unlocks, or 0."""
    window = settings.LOGIN_LOCKOUT_MINUTES * 60
    now = time.time()
    recent = [t for t in _failures.get(email, []) if now - t < window]
    _failures[email] = recent
    if len(recent) >= settings.LOGIN_MAX_FAILURES:
        return int(window - (now - recent[-settings.LOGIN_MAX_FAILURES]))
    return 0


def _record_failure(email: str) -> None:
    _failures.setdefault(email, []).append(time.time())


def _gotrue(path: str, payload: dict) -> httpx.Response:
    return httpx.post(
        f"{settings.SUPABASE_URL}/auth/v1/{path}",
        headers={"apikey": settings.SUPABASE_SERVICE_KEY, "Content-Type": "application/json"},
        json=payload, timeout=10.0,
    )


def _session(body: dict) -> dict:
    return {k: body.get(k) for k in ("access_token", "refresh_token", "expires_in", "expires_at", "token_type")}


def _check_lock(email: str) -> None:
    wait = _locked_for(email)
    if wait:
        raise HTTPException(status_code=423, detail=f"Too many failed attempts. Try again in {max(1, wait // 60)} minute(s).")


@router.post("/login", dependencies=[Depends(rate_limit("20/minute", "login"))])
def login(req: LoginRequest):
    email = req.email.lower()
    _check_lock(email)
    resp = _gotrue("token?grant_type=password", {"email": email, "password": req.password})
    if resp.status_code != 200:
        _record_failure(email)
        if _locked_for(email):
            logger.warning(f"Login locked for {email} after {settings.LOGIN_MAX_FAILURES} failures")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    _failures.pop(email, None)
    return _session(resp.json())


@router.post("/otp", dependencies=[Depends(rate_limit("5/minute", "otp"))])
def request_otp(req: OtpRequest):
    """Email a one-time code to an existing account. The reply never says whether the account exists."""
    email = req.email.lower()
    _check_lock(email)
    resp = _gotrue("otp", {"email": email, "create_user": False})
    if resp.status_code >= 500:
        raise HTTPException(status_code=502, detail="Could not send the code, try again")
    return {"ok": True, "message": "If the account exists, a code has been sent"}


@router.post("/otp/verify", dependencies=[Depends(rate_limit("10/minute", "otp-verify"))])
def verify_otp(req: OtpVerify):
    email = req.email.lower()
    _check_lock(email)
    resp = _gotrue("verify", {"type": "email", "email": email, "token": req.token})
    if resp.status_code != 200:
        _record_failure(email)
        raise HTTPException(status_code=401, detail="The code is wrong or has expired")
    _failures.pop(email, None)
    return _session(resp.json())


@router.get("/mfa-status")
def mfa_status(user: AuthenticatedUser = Depends(get_current_user)):
    """Whether this session still needs a TOTP step before reviewer and rule admin routes accept it."""
    return {
        "role": user.role,
        "aal": user.aal,
        "mfa_role": user.role in MFA_ROLES,
        "mfa_required": not mfa_satisfied(user),
    }
