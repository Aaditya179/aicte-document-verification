"""
Demo accounts, the two fictional institutions and one draft application each.

Run from backend/ with:  PYTHONPATH=. .venv/bin/python -m seed.demo

The Supabase project is shared with Nirikshan, so this script:
- creates only @proofpath.demo accounts and refuses to touch any other account;
- sets no app_metadata role on them, so Nirikshan (which reads that role) gives them no access;
- writes only to the proofpath schema.
Re-running it is safe: rows are matched on their natural keys and updated in place.

The full synthetic dataset (about 30 applications with generated documents) comes in phase 2.
"""
from core import demo
from core.config import settings
from core.db import db
from services import audit


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
    if not email.endswith(demo.DOMAIN):
        raise ValueError(f"Refusing to touch {email}: only {demo.DOMAIN} accounts are managed here")
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


def run():
    institutions = {i["code"]: _upsert("institutions", {**i, "is_fictional": True}, "code") for i in demo.INSTITUTIONS}

    for email, name, role, code, _ in demo.ACCOUNTS:
        user_id = _account(email, name)
        _upsert("members", {
            "user_id": user_id, "role": role, "full_name": name,
            "institution_id": institutions[code]["id"] if code else None,
        }, "user_id")
    print(f"{len(demo.ACCOUNTS)} accounts ready (password: {settings.DEMO_PASSWORD})")

    for code, category in (("INST-1001", "extension_of_approval"), ("INST-1002", "new_institution")):
        institution = institutions[code]
        app_code = f"{code}-2027-28-01"
        if db.fetch_one("applications", code=app_code):
            continue
        application = db.insert("applications", {
            "code": app_code, "institution_id": institution["id"], "category": category,
            "academic_year": "2027-28", "declared_total_area_sqm": 5200,
        })
        audit.record(None, "application_seeded", "application", application["id"], application["id"], {"code": app_code})
    print("2 draft applications ready")


if __name__ == "__main__":
    run()
