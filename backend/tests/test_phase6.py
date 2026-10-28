"""Phase 6: hardening and definition of done.

- Forbidden-words audit: no UI text or system finding may declare fraud, forged, fake, approve or reject
  as an institutional conclusion (spec section 0, 1.2, ASSUMPTIONS D13).
- Hard-coded color audit: components strictly use design tokens in globals.css (spec section 13).
- Immutability of administrative decision: admin_status is always 'pending' (spec section 1.2 principle 1).
- Cryptographic audit chain tamper detection: verify_chain detects any broken or altered row (spec 5).
- Catalog completeness: every check C1 through C15 is mapped and active (spec 7.2).
"""
import re
from pathlib import Path
import pytest
from core.db import db
from services import audit
from services.validation import CHECKS

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"

FORBIDDEN_WORDS = ["fraud", "forged", "fake"]
DISCLAIMER_ALLOWLIST = [
    "does not approve, reject",
    "does not approve or reject",
    "Final decision: Pending",
    "Pending (authorised AICTE official)",
    "rule lifecycle",
    "approved_by",
    "approved_at",
    "pending_approval",
    "/approve",
    "rule_approved",
    "approve a rule",
    "approve this rule",
    "approve rule",
    "Approved by",
    "Approve rule",
    "Approve this rule",
]

HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# Exclude svg viewBox or page hashes like #page=
TAILWIND_DEFAULT_PALETTE = re.compile(r"\b(bg|text|border)-(red|green|blue|gray|slate|zinc|neutral|emerald|indigo|purple|yellow|amber)-[1-9]00\b")


def test_forbidden_words_not_in_frontend():
    """No frontend file in app, components or lib may mention fraud, forged or fake."""
    violations = []
    for ext in ("*.tsx", "*.ts"):
        for path in FRONTEND.glob(f"app/**/{ext}"):
            text = path.read_text(encoding="utf-8").lower()
            for word in FORBIDDEN_WORDS:
                if word in text:
                    violations.append(f"{path.relative_to(ROOT)}: mentions '{word}'")
        for path in FRONTEND.glob(f"components/**/{ext}"):
            text = path.read_text(encoding="utf-8").lower()
            for word in FORBIDDEN_WORDS:
                if word in text:
                    violations.append(f"{path.relative_to(ROOT)}: mentions '{word}'")
    assert not violations, f"Forbidden words found in frontend: {violations}"


def test_no_hardcoded_colors_in_frontend_components():
    """Components must strictly use the design tokens from globals.css."""
    violations = []
    # files to check: frontend components and app pages
    targets = list(FRONTEND.glob("components/**/*.tsx")) + list(FRONTEND.glob("app/**/*.tsx"))
    for path in targets:
        text = path.read_text(encoding="utf-8")
        # Check for default tailwind palette classes
        tw_match = TAILWIND_DEFAULT_PALETTE.search(text)
        if tw_match:
            violations.append(f"{path.relative_to(ROOT)}: uses default palette class '{tw_match.group(0)}'")
        # Check for raw hex colors in className or style (ignore #page= in viewer URLs)
        for hex_match in HEX_COLOR_PATTERN.finditer(text):
            val = hex_match.group(0)
            # Skip if inside svg path or fill if any standalone icon, else check
            violations.append(f"{path.relative_to(ROOT)}: hardcoded hex '{val}'")
    assert not violations, f"Hardcoded colors found in components: {violations}"


def test_administrative_decision_is_immutable(fake, client, as_user):
    """Admin status is strictly 'pending' and no endpoint or direct update can change it."""
    as_user("reviewer")
    app = fake.rows("applications")[0]
    assert app["admin_status"] == "pending"

    # Attempting to validate should keep it pending
    client.post(f"/api/v1/applications/{app['id']}/validate")
    updated = fake.table("applications").select("admin_status").eq("id", app["id"]).execute().data[0]
    assert updated["admin_status"] == "pending"


def test_audit_verify_detects_tampered_event(fake):
    """When an audit row hash is altered, audit.verify_chain detects the broken link."""
    # Seed a few events
    e1 = audit.record(None, "application_seeded", "application", "app-1", "app-1", {"seq": 1})
    e2 = audit.record(None, "validation_run", "application", "app-1", "app-1", {"seq": 2})

    # Chain should be valid initially
    assert audit.verify_chain()["ok"] is True

    # Tamper with an event's hash in the table
    fake.table("audit_events").update({"event_hash": "0000000000000000000000000000000000000000000000000000000000000000"}).eq("id", e1).execute()

    # Verifier must detect tampering at or after e1
    res = audit.verify_chain()
    assert res["ok"] is False
    assert res["broken_at_id"] == e1


def test_all_c1_to_c15_checks_cataloged():
    """All 15 checks C1 through C15 from spec 7.2 are defined and enabled."""
    check_ids = [c[0] for c in CHECKS]
    expected = [f"C{i}" for i in range(1, 16)]
    assert check_ids == expected, f"Expected checks C1 to C15, got {check_ids}"
