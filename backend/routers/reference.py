"""Reference data, public demo accounts, the rule list and the audit check."""
from fastapi import APIRouter, Depends

from core import demo
from core.db import db
from core.security import AuthenticatedUser, require_role
from services import audit

router = APIRouter(tags=["Reference"])


@router.get("/demo/accounts")
async def demo_accounts():
    """The demo accounts for the welcome page's one-click sign-in. Public: all are fictional."""
    institutions = {i["code"]: i["name"] for i in demo.INSTITUTIONS}
    return [{"email": email, "full_name": name, "role": role, "institution": institutions.get(code), "description": about}
            for email, name, role, code, about in demo.ACCOUNTS]


@router.get("/reference")
async def reference(user: AuthenticatedUser = Depends(require_role(["institution", "reviewer", "rule_admin"]))):
    """Categories, document types and which documents each category requires."""
    return {
        "categories": db.fetch_all("categories"),
        "document_types": db.fetch_all("document_types"),
        "required_documents": db.fetch_all("required_documents"),
    }


@router.get("/rules")
async def list_rules(user: AuthenticatedUser = Depends(require_role(["rule_admin"]))):
    return db.table("rules").select("*").order("rule_code").order("version", desc=True).execute().data or []


@router.get("/audit/verify", tags=["Audit"])
async def verify_audit(user: AuthenticatedUser = Depends(require_role(["reviewer", "rule_admin"]))):
    return audit.verify_chain()
