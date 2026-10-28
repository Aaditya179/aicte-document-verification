"""The upload pipeline end to end against the in-memory database: init, upload, file check, reading, versions."""
import io

import pymupdf
from PIL import Image

from services import pipeline

API = "/api/v1"

FORM_TEMPLATES = [
    {"doc_type": "application_form", "field_name": "institution_code", "value_type": "text",
     "regex": r"^\s*Institution code\s*:\s*([A-Z0-9][A-Z0-9/-]*)", "group_index": 1, "required": True},
    {"doc_type": "application_form", "field_name": "declared_faculty_count", "value_type": "int",
     "regex": r"^\s*Number of faculty\s*:\s*([\d,]+)", "group_index": 1, "required": True},
]


def _pdf(lines: list[str]) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((50, 80 + 20 * i), line)
    return doc.tobytes()


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


def _upload(client, fake, filename, mime, data, doc_type="application_form", category=None):
    res = client.post(f"{API}/applications/app-a/documents/init", json={
        "doc_type": doc_type, "filename": filename, "mime": mime, "size": len(data), "category": category})
    assert res.status_code == 201, res.text
    body = res.json()
    fake.storage.files[body["upload"]["path"]] = data
    return body


def test_pdf_is_checked_hashed_and_read(fake, client, as_user):
    fake.table("extraction_templates").insert(FORM_TEMPLATES).execute()
    as_user("institution_a")
    body = _upload(client, fake, "Form 2027.pdf", "application/pdf",
                   _pdf(["Institution code: INST-1001", "Number of faculty: 24"]))
    assert body["upload"]["path"].startswith("inst-a/app-a/")
    assert body["upload"]["path"].endswith("-Form-2027.pdf")

    doc = client.post(f"{API}/documents/{body['document']['id']}/finalize").json()
    assert doc["integrity_status"] == "passed" and len(doc["sha256"]) == 64 and doc["page_count"] == 1

    fields = {f["field_name"]: f for f in fake.rows("extracted_fields")}
    assert fields["institution_code"]["field_value"] == "INST-1001"
    assert fields["declared_faculty_count"]["field_value"] == "24"
    assert fields["declared_faculty_count"]["page_number"] == 1
    assert fields["declared_faculty_count"]["source_method"] == "PDF_TEXT"
    stored = next(d for d in fake.rows("documents") if d["id"] == doc["id"])
    assert stored["processing_status"] == "done"
    assert [e["p_type"] for e in fake.audit] == ["document_upload_started", "document_finalized", "document_processed"]


def test_missing_required_field_goes_to_a_reviewer(fake, client, as_user):
    fake.table("extraction_templates").insert(FORM_TEMPLATES).execute()
    as_user("institution_a")
    body = _upload(client, fake, "form.pdf", "application/pdf", _pdf(["Institution code: INST-1001", "Nothing else here"]))
    client.post(f"{API}/documents/{body['document']['id']}/finalize")
    count = next(f for f in fake.rows("extracted_fields") if f["field_name"] == "declared_faculty_count")
    assert count["review_state"] == "needs_confirmation" and count["field_value"] is None


def test_renamed_file_fails_the_check_and_is_not_read(fake, client, as_user):
    fake.table("extraction_templates").insert(FORM_TEMPLATES).execute()
    as_user("institution_a")
    body = _upload(client, fake, "not_really_a_pdf.pdf", "application/pdf", _png())
    doc = client.post(f"{API}/documents/{body['document']['id']}/finalize").json()
    assert doc["integrity_status"] == "failed"
    assert "image/png" in doc["integrity_note"]
    assert doc["processing_status"] == "error"
    assert fake.rows("extracted_fields") == []


def test_finalize_before_upload_is_refused(fake, client, as_user):
    as_user("institution_a")
    res = client.post(f"{API}/applications/app-a/documents/init",
                      json={"doc_type": "application_form", "filename": "form.pdf", "mime": "application/pdf", "size": 10})
    assert client.post(f"{API}/documents/{res.json()['document']['id']}/finalize").status_code == 409


def test_new_upload_of_same_type_becomes_next_version(fake, client, as_user):
    as_user("institution_a")
    first = _upload(client, fake, "form.pdf", "application/pdf", _pdf(["Institution code: INST-1001"]))
    client.post(f"{API}/documents/{first['document']['id']}/finalize")
    second = _upload(client, fake, "form-v2.pdf", "application/pdf", _pdf(["Institution code: INST-1001", "v2"]))
    doc = client.post(f"{API}/documents/{second['document']['id']}/finalize").json()
    assert doc["version"] == 2 and doc["supersedes_id"] == first["document"]["id"]
    old = next(d for d in fake.rows("documents") if d["id"] == first["document"]["id"])
    assert old["status"] == "superseded"


def test_photos_of_different_categories_do_not_replace_each_other(fake, client, as_user):
    as_user("institution_a")
    lab = _upload(client, fake, "lab.png", "image/png", _png(), "infrastructure_photo", "lab")
    client.post(f"{API}/documents/{lab['document']['id']}/finalize")
    library = _upload(client, fake, "library.png", "image/png", _png(), "infrastructure_photo", "library")
    doc = client.post(f"{API}/documents/{library['document']['id']}/finalize").json()
    assert doc["version"] == 1
    assert {d["status"] for d in fake.rows("documents") if d["application_id"] == "app-a"} == {"current"}
    media = {m["category"]: m for m in fake.rows("media_assets")}
    assert len(media["lab"]["phash"]) == 16


def test_upload_metadata_is_checked_before_any_bytes(fake, client, as_user):
    as_user("institution_a")
    cases = [
        ({"filename": "form.exe", "mime": "application/pdf", "size": 10}, "PDF, JPEG or PNG"),
        ({"filename": "form.pdf", "mime": "image/png", "size": 10}, "does not match"),
        ({"filename": "form.pdf", "mime": "application/pdf", "size": 999 * 1024 * 1024}, "larger than"),
    ]
    for body, message in cases:
        res = client.post(f"{API}/applications/app-a/documents/init", json={"doc_type": "application_form", **body})
        assert res.status_code == 422 and message in res.json()["detail"]
    res = client.post(f"{API}/applications/app-a/documents/init", json={
        "doc_type": "infrastructure_photo", "filename": "lab.png", "mime": "image/png", "size": 10})
    assert res.status_code == 422 and "what the photo shows" in res.json()["detail"]


def test_submitted_application_takes_no_more_documents(fake, client, as_user):
    as_user("institution_a")
    body = _upload(client, fake, "form.pdf", "application/pdf", _pdf(["Institution code: INST-1001"]))
    client.post(f"{API}/documents/{body['document']['id']}/finalize")
    assert client.post(f"{API}/applications/app-a/submit").status_code == 200
    res = client.post(f"{API}/applications/app-a/documents/init",
                      json={"doc_type": "application_form", "filename": "late.pdf", "mime": "application/pdf", "size": 10})
    assert res.status_code == 409


def test_safe_filename():
    assert pipeline.safe_filename("../../etc/passwd") == "passwd"
    assert pipeline.safe_filename("Fire NOC (final).PDF") == "Fire-NOC-final-.pdf"
