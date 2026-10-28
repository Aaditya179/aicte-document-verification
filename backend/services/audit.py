"""
Hash-chained audit log in proofpath.audit_log.

Each entry's hash is SHA-256 of the previous entry's hash plus the canonical JSON of the entry,
so editing any stored row breaks the chain from that row on. Writes are not serialised across
processes, which is enough for a single API instance.
"""
import hashlib
import json
from typing import Any, Optional

from core.db import db
from core.security import AuthenticatedUser

GENESIS = "GENESIS"


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _plain(value: Any) -> Any:
    """The value as it will come back from a jsonb column, so hashing is stable across the round trip."""
    return None if value is None else json.loads(canonical(value))


def _payload(row: dict) -> str:
    return canonical({
        "actor": row.get("actor_id"),
        "role": row.get("actor_role"),
        "action": row.get("action"),
        "entity": [row.get("entity_type"), row.get("entity_id")],
        "before": row.get("before"),
        "after": row.get("after"),
        "reason": row.get("reason"),
    })


def _last_hash() -> str:
    res = db.table("audit_log").select("hash").order("seq", desc=True).limit(1).execute()
    return res.data[0]["hash"] if res.data else GENESIS


def record(
    actor: AuthenticatedUser,
    action: str,
    entity_type: str,
    entity_id: Optional[str],
    before: Optional[Any] = None,
    after: Optional[Any] = None,
    reason: Optional[str] = None,
) -> dict:
    entry = {
        "actor_id": actor.id,
        "actor_role": actor.role,
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id is not None else None,
        "before": _plain(before),
        "after": _plain(after),
        "reason": reason,
    }
    prev = _last_hash()
    entry["prev_hash"] = prev
    entry["hash"] = hashlib.sha256((prev + _payload(entry)).encode()).hexdigest()
    return db.insert("audit_log", entry) or entry


def verify_chain() -> dict:
    """Recompute every hash in order. Returns {ok: True, entries_verified} or the first broken seq."""
    rows, page = [], 1000
    while True:
        batch = db.table("audit_log").select("*").order("seq").range(len(rows), len(rows) + page - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page:
            break

    prev = GENESIS
    for row in rows:
        expected = hashlib.sha256((prev + _payload(row)).encode()).hexdigest()
        if row["prev_hash"] != prev or row["hash"] != expected:
            return {"ok": False, "broken_at_seq": row["seq"], "message": f"Hash mismatch at entry {row['seq']}"}
        prev = row["hash"]
    return {"ok": True, "entries_verified": len(rows)}
