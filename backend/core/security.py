"""
Sign-in and roles.

Accounts are shared with Nirikshan (one Supabase project, one auth.users), so a valid token alone
says nothing about ProofPath. The role comes only from proofpath.members; the account's app_metadata
holds the Nirikshan role and is ignored. An account with no member row gets 403.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import time
import httpx
import jwt
from supabase_auth.errors import AuthRetryableError

from core.config import settings
from core.db import db

security_scheme = HTTPBearer()

ROLES = {"institution", "reviewer", "rule_admin"}
# Roles that see every institution's data or change rules, and therefore need MFA
MFA_ROLES = {"reviewer", "rule_admin"}


class AuthenticatedUser(BaseModel):
    id: str
    email: Optional[str] = None
    role: str
    institution_id: Optional[str] = None
    full_name: Optional[str] = None
    aal: str = "aal1"


def _unverified_claims(token: str) -> dict:
    """Claims of a token already validated by Supabase; used only to read `aal`."""
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return {}


def _supabase_user(token: str):
    """
    The token's user as Supabase sees it. Dropped connections are retried, and an unreachable
    Supabase is a 503 so a network blip does not read as an expired session.
    """
    for attempt in range(3):
        try:
            res = db.client.auth.get_user(token)
            return res.user if res else None
        except (httpx.TransportError, AuthRetryableError):
            if attempt == 2:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                    detail="Sign-in service unreachable, please retry")
            time.sleep(0.2 * (attempt + 1))


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> AuthenticatedUser:
    token = credentials.credentials
    try:
        user = _supabase_user(token)
    except HTTPException:
        raise
    except Exception:
        user = None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired authentication credentials")

    member = db.fetch_one("members", user_id=user.id)
    if not member or member.get("role") not in ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has no ProofPath access")

    return AuthenticatedUser(
        id=user.id,
        email=user.email,
        role=member["role"],
        institution_id=member.get("institution_id"),
        full_name=member.get("full_name") or user.email,
        aal=_unverified_claims(token).get("aal") or "aal1",
    )


def mfa_satisfied(user: AuthenticatedUser) -> bool:
    """Reviewers and rule admins need a TOTP-verified (aal2) session; the demo bypass skips it."""
    if user.role not in MFA_ROLES or user.aal == "aal2":
        return True
    if settings.DEMO_MFA_BYPASS and (user.email or "").lower() not in settings.mfa_enforced_emails:
        return True
    return False


async def get_verified_user(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """The current user, rejected with `mfa_required` when MFA is still owed."""
    if not mfa_satisfied(user):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="mfa_required")
    return user


def require_role(allowed_roles: List[str]):
    """Only the listed roles pass. No role has implicit access to anything."""
    def role_checker(user: AuthenticatedUser = Depends(get_verified_user)) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied for role: {user.role}")
        return user
    return role_checker
