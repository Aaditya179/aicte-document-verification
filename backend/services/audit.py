"""
Append-only, hash-chained audit trail in proofpath.audit_events.

The chain is built inside Postgres: proofpath.audit_append takes a lock, reads the last hash and
inserts the new event with SHA-256(previous hash | its fields), so concurrent API workers cannot fork
the chain. proofpath.audit_verify recomputes every hash with the same formula. A trigger rejects any
update, delete or truncate.
"""
from typing import Any, Optional

from core.db import db
from core.security import AuthenticatedUser


def record(
    actor: Optional[AuthenticatedUser],
    event_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[Any] = None,
    application_id: Optional[str] = None,
    detail: Optional[dict] = None,
) -> int:
    """Append one event and return its id. `actor` is None for system events (background processing)."""
    res = db.rpc("audit_append", {
        "p_actor": actor.id if actor else None,
        "p_role": actor.role if actor else "system",
        "p_type": event_type,
        "p_entity_type": entity_type,
        "p_entity_id": str(entity_id) if entity_id is not None else None,
        "p_app": application_id,
        "p_detail": detail,
    }).execute()
    return res.data


def verify_chain() -> dict:
    """{ok, events_checked, broken_at_id}: the first event whose hash no longer matches, if any."""
    return db.rpc("audit_verify").execute().data
