from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.security import AuthenticatedUser, MFA_ROLES, get_current_user, mfa_satisfied, require_role
from routers import auth, cases
from services import audit

app = FastAPI(
    title="ProofPath AI API",
    description="Traceable case files for AICTE applications (SIH26261)",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:3001", "http://127.0.0.1:3001"],
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")
app.include_router(cases.patterns_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "proofpath-api", "version": app.version}


@app.get("/api/v1/health", tags=["Health"])
async def api_health_check():
    return {"status": "healthy", "service": "proofpath-api-v1"}


@app.get("/api/v1/me", tags=["Auth"])
async def get_me(user: AuthenticatedUser = Depends(get_current_user)):
    return {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "institution_id": user.institution_id,
        "full_name": user.full_name,
        "aal": user.aal,
        "mfa_role": user.role in MFA_ROLES,
        "mfa_required": not mfa_satisfied(user),
    }


@app.get("/api/v1/audit/verify", tags=["Audit"])
async def verify_audit(user: AuthenticatedUser = Depends(require_role(["auditor", "verifier", "analyst"]))):
    return audit.verify_chain()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
