from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.security import AuthenticatedUser, MFA_ROLES, get_current_user, mfa_satisfied
from routers import applications, auth, clauses, documents, findings, reference, rules, settings as settings_routes, verification, workflow

# Route handlers are plain `def`: supabase-py is blocking, and FastAPI runs a plain handler in a worker
# thread, so one request's database calls do not hold up the others.
app = FastAPI(
    title="ProofPath AI API",
    description="Evidence-first validation of AICTE applications (SIH26261). Decision support only.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

cors_origins = [o.strip().rstrip("/") for o in settings.FRONTEND_ORIGIN.split(",") if o.strip()]
cors_origins.extend(["http://localhost:3001", "http://127.0.0.1:3001"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or r"^https://.*\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, applications, documents, findings, reference, workflow, verification, rules, settings_routes, clauses):
    app.include_router(module.router, prefix="/api/v1")


@app.get("/", tags=["Root"])
def root():
    return {
        "service": "ProofPath AI API",
        "version": app.version,
        "status": "healthy",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "service": "proofpath-api", "version": app.version}


@app.get("/api/v1/health", tags=["Health"])
def api_health_check():
    return {"status": "healthy", "service": "proofpath-api-v1"}


@app.get("/api/v1/me", tags=["Auth"])
def get_me(user: AuthenticatedUser = Depends(get_current_user)):
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
