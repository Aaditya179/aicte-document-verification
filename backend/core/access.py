"""
Who may see which application. The service role bypasses row-level security, so these checks are
the only lock on the data (build spec 5.2, CLAUDE.md, assumption D4) and every route that loads an
application or document goes through them.

An institution sees only its own institution's applications. Anything else reads as 404, so an
institution cannot even learn that another institution's application exists.
"""
from typing import Optional

from fastapi import HTTPException

from core.db import db
from core.security import AuthenticatedUser

READ_ALL_ROLES = {"reviewer", "rule_admin"}
# States in which the institution may still add or replace documents
EDITABLE_STATES = {"draft", "awaiting_institution"}


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found")


def can_read_application(user: AuthenticatedUser, application: Optional[dict]) -> bool:
    if not application:
        return False
    if user.role in READ_ALL_ROLES:
        return True
    return user.role == "institution" and application["institution_id"] == user.institution_id


def application_for(user: AuthenticatedUser, application_id: str) -> dict:
    application = db.fetch_one("applications", id=application_id)
    if not can_read_application(user, application):
        raise _not_found("Application")
    return application


def document_for(user: AuthenticatedUser, document_id: str) -> tuple[dict, dict]:
    """The document and its application, if this user may read them."""
    document = db.fetch_one("documents", id=document_id)
    if not document:
        raise _not_found("Document")
    application = db.fetch_one("applications", id=document["application_id"])
    if not can_read_application(user, application):
        raise _not_found("Document")
    return document, application


def require_editable(application: dict) -> None:
    if application["workflow_status"] not in EDITABLE_STATES:
        raise HTTPException(status_code=409, detail="This application has been submitted; documents can no longer be changed")
