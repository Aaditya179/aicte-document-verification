from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # Same Supabase project as Nirikshan. ProofPath's tables live in their own schema.
    SUPABASE_URL: str = "http://127.0.0.1:54321"
    SUPABASE_SERVICE_KEY: str = "dummy_service_key"
    SUPABASE_JWT_SECRET: str = "dummy_secret_key_at_least_32_characters_long"
    SUPABASE_SCHEMA: str = "proofpath"
    FRONTEND_ORIGIN: str = "http://localhost:3001"
    # Extra origins allowed by CORS, as a regex, e.g. Vercel preview deployments
    CORS_ORIGIN_REGEX: Optional[str] = None
    DEMO_PASSWORD: str = "password123"
    PORT: int = 8001

    # Verifier and analyst routes need an aal2 token. DEMO_MFA_BYPASS lets demo accounts skip it,
    # except the accounts in DEMO_MFA_ENFORCED_EMAILS, which show the full flow. Off in any real deployment.
    DEMO_MFA_BYPASS: bool = False
    DEMO_MFA_ENFORCED_EMAILS: str = ""

    # LLM via Groq. The failsafe key is used when the default key fails. With neither set, AI runs in mock mode.
    GROQ_API_KEY: Optional[str] = None
    GROQ_API_KEY_FAILSAFE: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_VISION_MODEL: str = "qwen/qwen3.8-27b"

    # Documents: a private bucket of ProofPath's own, separate from Nirikshan's
    STORAGE_BUCKET: str = "proofpath-documents"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    SIGNED_LINK_TTL_SECONDS: int = 300

    # Login lockout
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    @field_validator("FRONTEND_ORIGIN")
    @classmethod
    def _no_trailing_slash(cls, v: str) -> str:
        # Browsers send Origin without a trailing slash
        return v.strip().rstrip("/")

    @property
    def mfa_enforced_emails(self) -> set:
        return {e.strip().lower() for e in self.DEMO_MFA_ENFORCED_EMAILS.split(",") if e.strip()}

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
