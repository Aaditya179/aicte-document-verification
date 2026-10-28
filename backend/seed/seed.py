"""
The synthetic dataset (build spec section 14): fictional institutions, 30 submitted applications with
generated documents and photos, and ground_truth.json listing exactly which findings each application
must produce. Everything is FICTIONAL and labelled so.

Run from backend/ after seed.demo:

    PYTHONPATH=. .venv/bin/python -m seed.seed            # create what is missing (safe to rerun)
    PYTHONPATH=. .venv/bin/python -m seed.seed --reset    # list what a reset would delete (dry run)
    PYTHONPATH=. .venv/bin/python -m seed.seed --reset --yes

Every document goes through the real pipeline (file check, then reading), so the evaluation
(scripts/evaluate.py) measures extraction and checks together. The as-of date is fixed at AS_OF in
proofpath.settings, so dates in the documents give the same findings on any day.

Phase 2 covers the within-application scenarios (checks C1 to C6). Cross-institution and
infrastructure scenarios join in phase 3.
"""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from core.db import db
from seed import make_documents as mk
from seed.make_documents import AppSpec, Person
from services import audit, pipeline

AS_OF = date(2026, 11, 1)
YEAR = "2027-28"
OUT = Path(__file__).parent / "generated"
GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

INSTITUTIONS = [
    ("INST-1001", "Aarohan Institute of Technology", "Pune"),
    ("INST-2001", "Godavari Institute of Engineering", "Nashik"),
    ("INST-2002", "Kaveri College of Technology", "Mysuru"),
    ("INST-2003", "Narmada Polytechnic", "Jabalpur"),
    ("INST-2004", "Sahyadri School of Engineering", "Satara"),
    ("INST-2005", "Tapti Institute of Science and Technology", "Surat"),
    ("INST-2006", "Mahanadi Engineering College", "Cuttack"),
    ("INST-2007", "Brahmaputra Institute of Technology", "Guwahati"),
    ("INST-2008", "Chambal College of Engineering", "Kota"),
    ("INST-2009", "Pennar Institute of Management", "Nellore"),
    ("INST-2010", "Sabarmati Technical Institute", "Ahmedabad"),
    ("INST-2011", "Vaigai College of Engineering", "Madurai"),
    ("INST-2012", "Krishna Valley Institute of Technology", "Vijayawada"),
    ("INST-2013", "Betwa Institute of Pharmacy", "Jhansi"),
    ("INST-2014", "Sutlej College of Architecture", "Ludhiana"),
    ("INST-2015", "Tungabhadra Engineering College", "Hospet"),
]

# Distinct given names and surnames; each person in the dataset gets a unique pair
GIVEN = ["Aditi", "Bhaskar", "Chitra", "Devendra", "Esha", "Farhan", "Gauri", "Harish", "Indu", "Jatin", "Kavya",
         "Lokesh", "Madhavi", "Nikhil", "Oviya", "Pranav", "Rashmi", "Sandeep", "Tanvi", "Uday", "Vaishali", "Yash",
         "Zoya", "Ankur", "Bhavna", "Chetan", "Deepa", "Eknath", "Firoza", "Girish", "Hema", "Ishaan"]
SURNAMES = ["Agarkar", "Bhosale", "Chaturvedi", "Dhillon", "Edathil", "Fernandes", "Gokhale", "Hegde", "Iyengar",
            "Jadhav", "Khanna", "Lobo", "Mukherjee", "Nambiar", "Ojha", "Pillai", "Qureshi", "Rathore", "Sengupta",
            "Thakur", "Upadhyay", "Venkatesh", "Wadia", "Yadav", "Zaveri", "Bandopadhyay", "Choudhury", "Dsouza",
            "Gill", "Hussain", "Kulkarni", "Mehrotra", "Naidu", "Pandey", "Rangan", "Saldanha", "Tiwari", "Vora"]
DESIGNATIONS = ["Professor", "Associate Professor", "Assistant Professor", "Assistant Professor"]
QUALIFICATIONS = ["PhD", "PhD", "M.Tech", "M.E."]


def _people(seq: int) -> list[Person]:
    out = []
    for j in range(4):
        n = seq * 4 + j
        out.append(Person(
            code=f"F-{j + 1:03d}", name=f"{'Dr. ' if QUALIFICATIONS[j] == 'PhD' else ''}{GIVEN[n % len(GIVEN)]} {SURNAMES[(n * 7) % len(SURNAMES)]}",
            designation=DESIGNATIONS[j], qualification=QUALIFICATIONS[j], masked_id=f"XXXX-XXXX-{2000 + n:04d}",
            start=date(2018 + (n % 6), 7, 1),
        ))
    return out


def clean_spec(seq: int, inst: tuple, category: str = "extension_of_approval") -> AppSpec:
    code, name, city = inst
    faculty = 20 + seq % 12
    return AppSpec(
        seq=seq, inst_code=code, inst_name=name, city=city, category=category, academic_year=YEAR,
        declared_faculty=faculty, faculty_total=faculty, faculty=_people(seq),
        declared_area_sqm=4200 + seq * 150, survey_no=f"{140 + seq}/{seq % 6 + 1}", land_area_sqm=20000 + seq * 900,
        certificate_no=f"AICTE-SYN/2025/{70000 + seq * 13}", certificate_code=code.replace("-", " ") if seq % 3 == 0 else code,
        cert_issue="1 April 2025", cert_expiry="31/03/2028", form_cert_valid_until="31 March 2028", form_code=code,
        noc_no=f"FIRE/{city[:4].upper()}/2026/{1100 + seq}", form_noc_no=f"FIRE/{city[:4].upper()}/2026/{1100 + seq}",
        noc_issue="15 January 2026", noc_expiry="14 January 2027", affidavit_date="20 September 2026",
        photo_taken=datetime(2026, 6 + seq % 4, 10, 11, 0, 0),
        skip={"approval_certificate"} if category == "new_institution" else {"land_document"},
    )


def scenarios() -> list[tuple[str, str, AppSpec, list[str]]]:
    """(scenario, note, spec, expected finding keys with {code} for the application code)."""
    inst = {i[0]: i for i in INSTITUTIONS}
    out = []

    def add(name, note, spec, expected):
        out.append((name, note, spec, expected))

    add("clean_control", "Every document consistent and in date; identifiers printed with different separators",
        # 2026-27, so it never collides with Aarohan's 2027-28 demo draft
        replace(clean_spec(0, inst["INST-1001"]), certificate_code="INST 1001", academic_year="2026-27"), [])
    add("date_conflict", "Form declares approval valid until 31 March 2029; the certificate says 31/03/2028",
        replace(clean_spec(1, inst["INST-2001"]), form_cert_valid_until="31 March 2029"), ["DATE_CONFLICT|{code}|CERT_VALIDITY"])
    add("count_conflict", "Form declares 24 faculty; the faculty list totals 22",
        replace(clean_spec(2, inst["INST-2002"]), declared_faculty=24, faculty_total=22), ["COUNT_CONFLICT|{code}|FACULTY_COUNT"])
    add("id_mismatch", "Institution code on the certificate differs from the form",
        replace(clean_spec(3, inst["INST-2003"]), certificate_code="INST-2030"), ["ID_MISMATCH|{code}|INST_CODE"])
    add("missing_document", "No fire NOC uploaded",
        replace(clean_spec(4, inst["INST-2004"]), skip={"land_document", "fire_noc"}), ["MISSING_DOCUMENT|{code}|fire_noc"])
    add("expired_document", "Approval certificate valid until 31/03/2026, before the as-of date 01/11/2026",
        replace(clean_spec(5, inst["INST-2005"]), cert_issue="1 April 2023", cert_expiry="31/03/2026",
                form_cert_valid_until="31 March 2026"), ["EXPIRED_DOCUMENT|{code}|approval_certificate"])
    add("duplicate_file", "The library photo was also uploaded as the floor plan",
        replace(clean_spec(6, inst["INST-2006"]), duplicate_of={"floor_plan": "library"}), ["DUPLICATE_FILE|{code}|{dup}"])
    add("low_confidence_date", "Certificate date of issue printed 03/08/2025: 3 August or 8 March",
        replace(clean_spec(7, inst["INST-2007"]), cert_issue="03/08/2025"),
        ["FIELD_NEEDS_CONFIRMATION|{code}|approval_certificate.issue_date"])
    add("date_order", "Fire NOC valid until a date before its date of issue",
        replace(clean_spec(8, inst["INST-2008"]), noc_issue="1 May 2027", noc_expiry="1 January 2027"),
        ["DATE_ORDER_INVALID|{code}|fire_noc"])

    # Clean applications, half of them new institutions: none may be flagged. An institution's second
    # application takes the other academic year, so every application code is unique.
    used = {app_code(spec) for _, _, spec, _ in out}
    fillers = INSTITUTIONS[9:] + INSTITUTIONS[1:9] + INSTITUTIONS[9:]
    for k, inst_row in enumerate(fillers[:21]):
        seq = 9 + k
        category = "new_institution" if k % 2 else "extension_of_approval"
        spec = clean_spec(seq, inst_row, category)
        if app_code(spec) in used:
            spec = replace(spec, academic_year="2026-27")
        assert app_code(spec) not in used, app_code(spec)
        used.add(app_code(spec))
        add("clean", "Consistent documents" + (" (new institution, with land document)" if category == "new_institution" else ""), spec, [])
    return out


def app_code(spec: AppSpec) -> str:
    return f"{spec.inst_code}-{spec.academic_year}-01"


def documents_for(spec: AppSpec) -> list[tuple[str, str, str, bytes, str | None]]:
    """(doc_type, filename, mime, bytes, photo category) for every document of the application."""
    docs = []
    for doc_type, builder in mk.PDF_BUILDERS.items():
        if doc_type in spec.skip or doc_type in spec.duplicate_of:
            continue
        docs.append((doc_type, f"{doc_type}.pdf", "application/pdf", builder(spec), None))
    photos = {c: mk.photo(spec, c) for c in spec.photo_categories}
    for c, data in photos.items():
        docs.append(("infrastructure_photo", f"{c}_photo.jpg", "image/jpeg", data, c))
    for doc_type, category in spec.duplicate_of.items():
        docs.append((doc_type, f"{doc_type}.jpg", "image/jpeg", photos[category], None))
    return docs


def _upload(application: dict, doc_type: str, filename: str, mime: str, data: bytes, category: str | None) -> None:
    import uuid
    document_id = str(uuid.uuid4())
    path = pipeline.storage_path(application, document_id, filename)
    db.storage.upload(path, data, {"content-type": mime, "upsert": "false"})
    document = db.insert("documents", {
        "id": document_id, "application_id": application["id"], "doc_type": doc_type, "storage_path": path,
        "original_name": filename, "mime": mime, "size_bytes": len(data), "version": 1, "status": "current",
        "integrity_status": "pending", "processing_status": "pending",
    })
    if category:
        db.insert("media_assets", {"document_id": document_id, "category": category})
    _, read_next = pipeline.finalize(None, document)
    if read_next:
        pipeline.process_document(document_id)


def build(spec: AppSpec, institution_id: str, deadline: date) -> tuple[str, bool]:
    code = app_code(spec)
    if db.fetch_one("applications", code=code):
        return code, False
    application = db.insert("applications", {
        "code": code, "institution_id": institution_id, "category": spec.category, "academic_year": spec.academic_year,
        "declared_total_area_sqm": spec.declared_area_sqm, "workflow_status": "submitted",
        "submitted_at": datetime(2026, 10, 1 + spec.seq % 25, 10, 0).isoformat() + "+05:30",
        "review_deadline": deadline.isoformat(),
    })
    for doc_type, filename, mime, data, category in documents_for(spec):
        folder = OUT / code
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_bytes(data)
        _upload(application, doc_type, filename, mime, data, category)
    audit.record(None, "application_seeded", "application", application["id"], application["id"], {"code": code, "synthetic": True})
    return code, True


def ground_truth(rows) -> dict:
    apps = {}
    for name, note, spec, expected in rows:
        code = app_code(spec)
        dup = ""
        if spec.duplicate_of:
            category = next(iter(spec.duplicate_of.values()))
            dup = hashlib.sha256(mk.photo(spec, category)).hexdigest()[:16]
        apps[code] = {"scenario": name, "note": note, "expected": [k.format(code=code, dup=dup) for k in expected]}
    return {
        "note": "Synthetic dataset. Every institution, person and document is fictional; rules are illustrative.",
        "as_of": AS_OF.isoformat(),
        "clean_control": next(c for c, a in apps.items() if a["scenario"] == "clean_control"),
        "applications": apps,
    }


def reset(confirm: bool) -> None:
    codes = [app_code(spec) for _, _, spec, _ in scenarios()]
    existing = db.table("applications").select("id,code").in_("code", codes).execute().data or []
    docs = db.table("documents").select("id,storage_path").in_("application_id", [a["id"] for a in existing] or ["00000000-0000-0000-0000-000000000000"]).execute().data or []
    print(f"A reset deletes {len(existing)} seeded applications and their {len(docs)} documents, findings and runs.")
    print("Only applications listed in ground_truth.json are touched; demo drafts and Nirikshan data are not. Audit events stay.")
    if not confirm:
        print("Dry run only. Add --yes to delete.")
        return
    paths = [d["storage_path"] for d in docs if d.get("storage_path")]
    for i in range(0, len(paths), 100):
        db.storage.remove(paths[i:i + 100])
    for a in existing:
        db.table("evidence_requests").delete().eq("application_id", a["id"]).execute()
        db.table("case_file_snapshots").delete().eq("application_id", a["id"]).execute()
        db.table("applications").delete().eq("id", a["id"]).execute()
    print(f"Deleted {len(existing)} applications.")


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    if args.reset:
        reset(args.yes)
        return

    db.table("settings").upsert({"key": "as_of", "value": {"mode": "fixed", "date": AS_OF.isoformat()}}, on_conflict="key").execute()
    institutions = {}
    for code, name, city in INSTITUTIONS:
        institutions[code] = db.table("institutions").upsert({"code": code, "name": name, "city": city, "is_fictional": True},
                                                            on_conflict="code").execute().data[0]["id"]
    rows = scenarios()
    GROUND_TRUTH.write_text(json.dumps(ground_truth(rows), indent=2) + "\n")

    def one(row):
        _, _, spec, _ = row
        # Deadlines spread from 3 to 40 days after the as-of date, so the priority's deadline bonus varies
        return build(spec, institutions[spec.inst_code], AS_OF + timedelta(days=3 + (spec.seq * 7) % 38))

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(one, rows))
    made = sum(1 for _, new in results if new)
    print(f"As-of date fixed at {AS_OF:%d/%m/%Y}. {made} applications created, {len(results) - made} already present.")
    print(f"Ground truth written to {GROUND_TRUTH}")


if __name__ == "__main__":
    run()
