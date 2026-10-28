"""
Demo data for ProofPath: accounts, two institutions, two case files and one cross-institution pattern.

Run from backend/ with:  PYTHONPATH=. .venv/bin/python -m seed.demo

The Supabase project is shared with Nirikshan, so this script:
- creates only @proofpath.demo accounts and refuses to touch any other account;
- sets no app_metadata role on them, so Nirikshan (which reads that role) gives them no access;
- writes only to the proofpath schema.
Re-running it is safe: rows are matched on their natural keys and updated in place.
"""
from core.config import settings
from core.db import db

DOMAIN = "@proofpath.demo"

INSTITUTIONS = [
    {"aicte_id": "PP-1-0001", "name": "Demo Institute of Technology", "state": "Maharashtra", "city": "Pune"},
    {"aicte_id": "PP-1-0002", "name": "Sahyadri College of Engineering", "state": "Maharashtra", "city": "Satara"},
]

ACCOUNTS = [
    ("institution@proofpath.demo", "Demo Institute (principal)", "institution", "PP-1-0001"),
    ("verifier@proofpath.demo", "Document verifier", "verifier", None),
    ("analyst@proofpath.demo", "Pattern analyst", "analyst", None),
    ("auditor@proofpath.demo", "Auditor", "auditor", None),
    ("admin@proofpath.demo", "Administrator", "admin", None),
]


def _find_user_id(email: str):
    page = 1
    while True:
        users = db.client.auth.admin.list_users(page=page, per_page=200)
        for u in users:
            if (u.email or "").lower() == email:
                return u.id
        if len(users) < 200:
            return None
        page += 1


def _account(email: str, full_name: str) -> str:
    if not email.endswith(DOMAIN):
        raise ValueError(f"Refusing to touch {email}: only {DOMAIN} accounts are managed here")
    user_id = _find_user_id(email)
    if user_id:
        db.client.auth.admin.update_user_by_id(user_id, {"password": settings.DEMO_PASSWORD})
        return user_id
    created = db.client.auth.admin.create_user({
        "email": email, "password": settings.DEMO_PASSWORD, "email_confirm": True,
        "user_metadata": {"full_name": full_name, "app": "proofpath"},
    })
    return created.user.id


def _upsert(table: str, row: dict, key: str) -> dict:
    return db.table(table).upsert(row, on_conflict=key).execute().data[0]


def _fact(case_id: str, doc_id: str, field: str, text: str, **extra) -> str:
    row = {"case_id": case_id, "document_id": doc_id, "field": field, "value_text": text, **extra}
    existing = db.table("facts").select("id").eq("document_id", doc_id).eq("field", field).limit(1).execute().data
    if existing:
        db.table("facts").update(row).eq("id", existing[0]["id"]).execute()
        return existing[0]["id"]
    return db.insert("facts", row)["id"]


def _document(case_id: str, doc_type: str, title: str, sha256: str) -> str:
    row = {"case_id": case_id, "doc_type": doc_type, "title": title, "sha256": sha256, "mime_type": "application/pdf", "page_count": 4}
    existing = db.table("documents").select("id").eq("case_id", case_id).eq("doc_type", doc_type).limit(1).execute().data
    if existing:
        db.table("documents").update(row).eq("id", existing[0]["id"]).execute()
        return existing[0]["id"]
    return db.insert("documents", row)["id"]


def run():
    inst = {i["aicte_id"]: _upsert("institutions", i, "aicte_id") for i in INSTITUTIONS}

    for email, name, role, aicte_id in ACCOUNTS:
        user_id = _account(email, name)
        _upsert("members", {
            "user_id": user_id, "role": role, "full_name": name,
            "institution_id": inst[aicte_id]["id"] if aicte_id else None,
        }, "user_id")
    print(f"{len(ACCOUNTS)} accounts ready (password: {settings.DEMO_PASSWORD})")

    # Case 1: one field verified, one in conflict, one unverified
    c1 = _upsert("cases", {"case_no": "PP-2027-0001", "institution_id": inst["PP-1-0001"]["id"],
                           "application_type": "extension_of_approval", "academic_year": "2027-28",
                           "status": "in_review"}, "case_no")
    lease = _document(c1["id"], "lease", "Registered lease deed", "a1" * 32)
    plan = _document(c1["id"], "building_plan", "Approved building plan", "b2" * 32)
    fire = _document(c1["id"], "fire_noc", "Fire NOC", "c3" * 32)

    name_lease = _fact(c1["id"], lease, "institution_name", "Demo Inst. of Tech.", page=1,
                       source_quote="Lessee: Demo Inst. of Tech., Pune", confidence=0.97,
                       match_key="demo institute technology")
    name_plan = _fact(c1["id"], plan, "institution_name", "Demo Institute of Technology", page=1,
                      source_quote="Applicant: Demo Institute of Technology", confidence=0.99,
                      match_key="demo institute technology")
    area_lease = _fact(c1["id"], lease, "land_area", "10 acres", page=2, value_norm={"sq_m": 40468.6},
                       source_quote="admeasuring 10 acres", confidence=0.95)
    area_plan = _fact(c1["id"], plan, "land_area", "3.2 hectares", page=1, value_norm={"sq_m": 32000},
                      source_quote="Total plot area: 3.2 ha", confidence=0.93)
    survey = _fact(c1["id"], lease, "survey_no", "S. No. 112-3", page=2, match_key="112/3",
                   source_quote="bearing S. No. 112-3, village Hinjawadi", confidence=0.9)
    noc = _fact(c1["id"], fire, "valid_until", "31/03/2028", page=1, value_norm={"date": "2028-03-31"},
                source_quote="Valid up to 31/03/2028", confidence=0.62)

    for check in [
        {"field": "institution_name", "status": "verified", "fact_ids": [name_lease, name_plan], "rule": "name_match",
         "reason": "The lease and the building plan name the same institution once abbreviations are expanded."},
        {"field": "land_area", "status": "conflict", "fact_ids": [area_lease, area_plan], "rule": "area_tolerance_2pct",
         "reason": "The lease gives 10 acres (40,469 m²) and the building plan 3.2 ha (32,000 m²), 21% apart; the limit is 2%."},
        {"field": "fire_noc_validity", "status": "unverified", "fact_ids": [noc], "rule": "ocr_confidence",
         "reason": "The expiry date was read with 62% confidence and no officer has confirmed it yet."},
    ]:
        _upsert("checks", {"case_id": c1["id"], **check}, "case_id,field")

    # Case 2, another institution, leasing the same survey number: invisible from either case alone
    c2 = _upsert("cases", {"case_no": "PP-2027-0002", "institution_id": inst["PP-1-0002"]["id"],
                           "application_type": "new_institution", "academic_year": "2027-28",
                           "status": "open"}, "case_no")
    lease2 = _document(c2["id"], "lease", "Lease deed", "d4" * 32)
    survey2 = _fact(c2["id"], lease2, "survey_no", "Survey No. 112/3", page=1, match_key="112/3",
                    source_quote="Survey No. 112/3, Hinjawadi", confidence=0.94)
    _upsert("checks", {"case_id": c2["id"], "field": "survey_no", "status": "conflict", "fact_ids": [survey2],
                       "rule": "parcel_unique",
                       "reason": "The same land parcel is declared by another institution's application."}, "case_id,field")

    _upsert("patterns", {
        "kind": "same_land_parcel", "match_key": "112/3", "severity": "high",
        "summary": "Two institutions declare survey number 112/3 in Hinjawadi as their campus land.",
        "institution_ids": [inst["PP-1-0001"]["id"], inst["PP-1-0002"]["id"]],
        "case_ids": [c1["id"], c2["id"]], "fact_ids": [survey, survey2],
    }, "kind,match_key")

    print("2 case files and 1 cross-institution pattern ready")


if __name__ == "__main__":
    run()
