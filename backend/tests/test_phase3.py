"""Phase 3: checks C7 to C12 (one passing and one failing case each), the perceptual hash of a re-saved
copy, and the workflow routes: room table, confirming and correcting a value, evidence requests,
notifications, the priority queue and the cross-institution list."""
import io
import random
from datetime import date

from PIL import Image, ImageDraw

from services import crossinst
from services.extraction import hamming, phash
from services.validation import Context, evaluate, run_validation

API = "/api/v1"
AS_OF = date(2026, 11, 1)
RULES = {
    "R-ID-REUSE": {"rule_code": "R-ID-REUSE", "version": 1, "params": {}},
    "R-GHOST-01": {"rule_code": "R-GHOST-01", "version": 2, "params": {"similarity": 0.9}},
    "R-PHOTO-01": {"rule_code": "R-PHOTO-01", "version": 1, "params": {"max_hamming": 8}},
    "R-INFRA-01": {"rule_code": "R-INFRA-01", "version": 1, "params": {"required": ["lab", "classroom", "library", "floor_plan"]}},
    "R-AREA-01": {"rule_code": "R-AREA-01", "version": 1, "params": {"area_tolerance_pct": 1, "min_area_sqm": 4000}},
    "R-PHOTOAGE-01": {"rule_code": "R-PHOTOAGE-01", "version": 1, "params": {"max_photo_age_months": 12}},
}
DOC_TYPES = {t: {"code": t, "label": t.replace("_", " ").capitalize(), "has_expiry": False}
             for t in ("application_form", "faculty_list", "floor_plan", "infrastructure_photo", "land_document")}


def d(id_, doc_type, app="app"):
    return {"id": id_, "application_id": app, "doc_type": doc_type, "integrity_status": "passed", "status": "current",
            "version": 1, "sha256": f"sha-{id_}", "original_name": f"{id_}.pdf", "mime": "application/pdf"}


def person(code, name, qual="PhD", masked="XXXX-XXXX-1000", start="2021-07-01", end=None, doc="fac", inst="inst-a"):
    from services import normalise
    return {"faculty_code": code, "name_raw": name, "name_norm": normalise.name(name), "qualification": qual,
            "masked_id": masked, "period_start": start, "period_end": end, "document_id": doc, "page_number": 1,
            "institution_id": inst}


def base(**kw) -> Context:
    documents = [d("form", "application_form"), d("fac", "faculty_list"), d("plan", "floor_plan"), d("land", "land_document"),
                 d("lab", "infrastructure_photo"), d("cls", "infrastructure_photo"), d("lib", "infrastructure_photo")]
    taken = "2026-06-10T11:00:00+00:00"
    ctx = Context(
        application={"id": "app", "code": "APP-1", "institution_id": "inst-a", "declared_total_area_sqm": 4500},
        as_of=AS_OF, documents=documents,
        fields={"form": [{"field_name": "declared_total_area_sqm", "field_value": "4500", "original_value": "4,500",
                          "value_type": "number", "page_number": 1, "review_state": "auto"}],
                "land": [{"field_name": "survey_no", "field_value": "141/2", "original_value": "141/2", "value_type": "text",
                          "page_number": 1, "review_state": "auto"}]},
        doc_types=DOC_TYPES, required=[], pairs=[], rules=RULES,
        media={"lab": {"document_id": "lab", "category": "lab", "phash": "f0f0f0f0f0f0f0f0", "taken_at": taken},
               "cls": {"document_id": "cls", "category": "classroom", "phash": "0123456789abcdef", "taken_at": taken},
               "lib": {"document_id": "lib", "category": "library", "phash": "aaaaaaaaaaaaaaaa", "taken_at": taken}},
        faculty=[person("F-001", "Dr. Rohini Deshpande")],
        rooms=[{"room_label": "Block", "length_m": 50, "width_m": 90, "area_sqm": 4500}],
        cross=crossinst.CrossData(),
    )
    for k, v in kw.items():
        setattr(ctx, k, v)
    return ctx


def other(**kw) -> crossinst.CrossData:
    """Another institution's submitted application, with whatever claims the test gives it."""
    data = crossinst.CrossData(
        applications={"oth": {"id": "oth", "code": "OTH-1", "institution_id": "inst-b", "institution": {"name": "Other College"}}},
        documents={i: d(i, t, "oth") for i, t in (("o-fac", "faculty_list"), ("o-land", "land_document"), ("o-lab", "infrastructure_photo"))},
    )
    for k, v in kw.items():
        setattr(data, k, v)
    return data


def keys(ctx) -> set[str]:
    return {f.key for f in evaluate(ctx)[0]}


def test_the_clean_base_has_no_findings():
    assert keys(base()) == set()


# C7 ---------------------------------------------------------------------------------------------

def test_c7_reused_survey_number_is_flagged_across_institutions():
    cross = other(identifiers=[{"id": "x", "document_id": "o-land", "field_name": "survey_no", "field_value": "141-2",
                                "original_value": "141-2", "page_number": 1, "review_state": "auto"}])
    findings = evaluate(base(cross=cross))[0]
    assert [f.key for f in findings] == ["REUSED_IDENTIFIER|APP-1|OTH-1|survey_no"]
    assert findings[0].is_cross_institution and findings[0].related_application_id == "oth"


def test_c7_different_number_is_not_flagged():
    cross = other(identifiers=[{"id": "x", "document_id": "o-land", "field_name": "survey_no", "field_value": "141/3",
                                "page_number": 1, "review_state": "auto"}])
    assert keys(base(cross=cross)) == set()


# C8 ---------------------------------------------------------------------------------------------

def test_c8_name_variant_with_same_qualification_and_overlap_is_flagged():
    cross = other(faculty=[person("F-009", "Rohini S. Deshpande", masked="XXXX-XXXX-9999", start="2023-07-01", doc="o-fac", inst="inst-b")])
    findings = evaluate(base(cross=cross))[0]
    assert [f.key for f in findings] == ["GHOST_FACULTY|APP-1|OTH-1|F-001"]
    assert "Rohini" not in findings[0].title                      # list views show masked IDs, not names
    assert "Candidate for review, not proof" in findings[0].detail


def test_c8_same_masked_id_is_flagged_whatever_the_name():
    cross = other(faculty=[person("F-002", "R. Deshpande-Kulkarni", qual="M.Tech", masked="XXXX-XXXX-1000", doc="o-fac", inst="inst-b")])
    assert keys(base(cross=cross)) == {"GHOST_FACULTY|APP-1|OTH-1|F-001"}


def test_c8_lookalike_with_different_qualification_is_not_flagged():
    cross = other(faculty=[person("F-002", "Rohini Deshpande", qual="M.Tech", masked="XXXX-XXXX-7020", doc="o-fac", inst="inst-b")])
    assert keys(base(cross=cross)) == set()


def test_c8_periods_that_do_not_overlap_are_not_flagged():
    cross = other(faculty=[person("F-002", "Rohini Deshpande", masked="XXXX-XXXX-1000", start="2015-07-01", end="2020-06-30",
                                  doc="o-fac", inst="inst-b")])
    assert keys(base(cross=cross)) == set()


def test_c8_shared_given_name_is_not_flagged_at_version_2_similarity():
    cross = other(faculty=[person("F-002", "Dr. Rohini Rangan", masked="XXXX-XXXX-5555", doc="o-fac", inst="inst-b")])
    assert keys(base(cross=cross)) == set()


# C9 ---------------------------------------------------------------------------------------------

def _photo(seed: int) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", (1200, 800), tuple(rng.randint(150, 235) for _ in range(3)))
    draw = ImageDraw.Draw(img)
    for _ in range(8):
        x, y = rng.randint(0, 1000), rng.randint(60, 600)
        draw.rectangle([x, y, x + rng.randint(60, 320), y + rng.randint(40, 260)], fill=tuple(rng.randint(0, 255) for _ in range(3)))
    return img


def test_c9_resized_resaved_copy_keeps_a_close_fingerprint():
    original = _photo(7)
    buf = io.BytesIO()
    original.resize((1000, 667)).save(buf, "JPEG", quality=70)
    copy = Image.open(io.BytesIO(buf.getvalue()))
    assert hamming(phash(original), phash(copy)) <= 8
    assert hamming(phash(original), phash(_photo(8))) > 8


def test_c9_photo_within_max_hamming_is_flagged():
    cross = other(photos=[{"document_id": "o-lab", "category": "lab", "phash": "f0f0f0f0f0f0f0f1"}])
    assert keys(base(cross=cross)) == {"PHOTO_REUSE|APP-1|OTH-1"}


def test_c9_different_photo_is_not_flagged():
    cross = other(photos=[{"document_id": "o-lab", "category": "lab", "phash": "0f0f0f0f0f0f0f0f"}])
    assert keys(base(cross=cross)) == set()


def test_cross_checks_are_skipped_without_cross_data():
    ctx = base(cross=None)
    findings, evaluated = evaluate(ctx)
    assert findings == [] and not evaluated & {"REUSED_IDENTIFIER", "GHOST_FACULTY", "PHOTO_REUSE"}


# C10 --------------------------------------------------------------------------------------------

def test_c10_missing_library_photo_is_flagged():
    ctx = base()
    ctx.documents = [x for x in ctx.documents if x["id"] != "lib"]
    assert keys(ctx) == {"INFRA_EVIDENCE_MISSING|APP-1|library"}


def test_c10_floor_plan_left_to_c1_when_it_is_a_required_document():
    ctx = base(required=[{"doc_type": "floor_plan", "mandatory": True}])
    ctx.documents = [x for x in ctx.documents if x["id"] != "plan"]
    assert "INFRA_EVIDENCE_MISSING|APP-1|floor_plan" not in keys(ctx)


# C11 --------------------------------------------------------------------------------------------

def test_c11_rooms_short_of_the_declared_area_are_flagged():
    ctx = base(rooms=[{"room_label": "Block", "length_m": 50, "width_m": 82.8, "area_sqm": 4140}])   # 8% short
    findings = evaluate(ctx)[0]
    assert [f.key for f in findings] == ["AREA_MISMATCH|APP-1|total"]
    assert "4,140.00" in findings[0].title and "4,500.00" in findings[0].title


def test_c11_within_tolerance_and_above_minimum_is_not_flagged():
    assert keys(base(rooms=[{"room_label": "Block", "length_m": 50, "width_m": 89.6, "area_sqm": 4480}])) == set()


def test_c11_area_below_minimum_is_flagged():
    ctx = base(rooms=[])
    ctx.fields["form"][0].update(field_value="3600", original_value="3,600")
    assert keys(ctx) == {"AREA_BELOW_MINIMUM|APP-1|minimum"}


# C12 --------------------------------------------------------------------------------------------

def test_c12_photo_older_than_twelve_months_is_flagged():
    ctx = base()
    ctx.media["lab"] = {**ctx.media["lab"], "taken_at": "2025-06-15T10:30:00+00:00"}
    assert keys(ctx) == {"PHOTO_METADATA|APP-1|lab"}


def test_c12_missing_exif_is_a_finding_only_when_the_rule_requires_it():
    ctx = base()
    ctx.media["lab"] = {**ctx.media["lab"], "taken_at": None}
    assert keys(ctx) == set()
    ctx.rules = {**RULES, "R-PHOTOAGE-01": {**RULES["R-PHOTOAGE-01"], "params": {"max_photo_age_months": 12, "require_exif": True}}}
    assert keys(ctx) == {"PHOTO_METADATA|APP-1|lab"}


# Routes -----------------------------------------------------------------------------------------

def _submitted_with_unclear_date(fake):
    """app-a submitted, with a certificate whose issue date is ambiguous, and one full run done."""
    fake.table("settings").insert([{"key": "as_of", "value": {"mode": "fixed", "date": "2026-11-01"}}]).execute()
    fake.table("priority_weights").insert([{"key": "needs_confirmation", "weight": 10}, {"key": "conflict", "weight": 20}]).execute()
    fake.table("document_types").insert([{"code": "approval_certificate", "label": "Approval certificate", "has_expiry": True,
                                          "signature_required": True, "is_photo": False}]).execute()
    fake.table("rules").insert([{"rule_code": c, "version": 1, "status": "active", "effective_from": "2026-01-01", "effective_to": None,
                                 "params": {}} for c in ("R-OCR-01", "R-DATE-01")]).execute()
    fake.table("documents").insert([{"id": "cert-a", "application_id": "app-a", "doc_type": "approval_certificate", "version": 1,
                                     "status": "current", "integrity_status": "passed", "sha256": "3" * 64, "uploaded_at": "2026-10-01",
                                     "original_name": "certificate.pdf"}]).execute()
    fake.table("extracted_fields").insert([
        {"id": "f-issue", "document_id": "cert-a", "field_name": "issue_date", "field_value": "2025-08-03", "original_value": "03/08/2025",
         "value_type": "date", "page_number": 1, "review_state": "needs_confirmation",
         "review_reason": '"03/08/2025" could be 3 August 2025 or 8 March 2025'},
        {"id": "f-expiry", "document_id": "cert-a", "field_name": "expiry_date", "field_value": "2025-06-01", "original_value": "1 June 2025",
         "value_type": "date", "page_number": 1, "review_state": "auto"},
    ]).execute()
    fake.table("applications").update({"workflow_status": "submitted", "review_deadline": "2026-11-05"}).eq("id", "app-a").execute()
    run_validation("app-a", "full")


def test_confirming_a_value_records_it_and_revalidates(fake, client, as_user):
    _submitted_with_unclear_date(fake)
    assert [f["status"] for f in fake.rows("findings")] == ["open"]
    as_user("reviewer")
    res = client.post(f"{API}/fields/f-issue/confirm", json={"reason": "Certificate register shows 3 August 2025"})
    assert res.status_code == 200
    assert res.json()["field"]["review_state"] == "confirmed"
    # The confirmed date now takes part: the C5 finding closes and the expiry before issue shows (C3)
    by_key = {f["finding_key"]: f["status"] for f in fake.rows("findings")}
    assert by_key["FIELD_NEEDS_CONFIRMATION|INST-1001-2027-28-01|approval_certificate.issue_date"] == "auto_closed"
    assert by_key["DATE_ORDER_INVALID|INST-1001-2027-28-01|approval_certificate"] == "open"
    assert any(a["action"] == "confirm_field" and a["field_id"] == "f-issue" for a in fake.rows("review_actions"))


def test_correcting_a_value_keeps_the_original(fake, client, as_user):
    _submitted_with_unclear_date(fake)
    as_user("reviewer")
    assert client.post(f"{API}/fields/f-issue/correct", json={"value": "03/08/2025", "reason": "x" * 5}).status_code == 422
    res = client.post(f"{API}/fields/f-issue/correct", json={"value": "8 March 2025", "reason": "Issuing office confirmed 8 March"})
    field = res.json()["field"]
    assert (field["field_value"], field["original_value"], field["review_state"]) == ("2025-03-08", "03/08/2025", "corrected")
    as_user("institution_a")
    assert client.post(f"{API}/fields/f-issue/confirm", json={"reason": "mine"}).status_code == 403


def test_room_table_rules(fake, client, as_user):
    as_user("institution_a")
    rooms = {"rooms": [{"room_label": "Lab 1", "length_m": 20, "width_m": 15}, {"room_label": "Library", "length_m": 25, "width_m": 20}]}
    res = client.post(f"{API}/applications/app-a/rooms", json=rooms)
    assert res.status_code == 200 and res.json()["total_sqm"] == 800
    as_user("institution_b")
    assert client.post(f"{API}/applications/app-a/rooms", json=rooms).status_code == 404
    fake.table("applications").update({"workflow_status": "submitted"}).eq("id", "app-a").execute()
    as_user("institution_a")
    assert client.post(f"{API}/applications/app-a/rooms", json=rooms).status_code == 409
    as_user("reviewer")
    assert client.post(f"{API}/applications/app-a/rooms", json={"rooms": rooms["rooms"][:1]}).json()["total_sqm"] == 300


def test_evidence_request_round_trip(fake, client, as_user):
    _submitted_with_unclear_date(fake)
    finding = fake.rows("findings")[0]
    as_user("reviewer")
    client.post(f"{API}/findings/{finding['id']}/actions", json={"action": "request_evidence", "reason": "Send the issuing office's letter"})
    assert fake.rows("applications")[0]["workflow_status"] == "awaiting_institution"

    as_user("institution_a")
    requests = client.get(f"{API}/evidence-requests").json()
    assert [(r["status"], r["finding"]["title"]) for r in requests] == [("open", finding["title"])]
    notes = client.get(f"{API}/notifications").json()
    assert notes["unread"] == 1 and "asked for evidence" in notes["items"][0]["message"]
    as_user("institution_b")
    assert client.get(f"{API}/evidence-requests").json() == []
    assert client.post(f"{API}/evidence-requests/{requests[0]['id']}/fulfil", json={"note": "attached"}).status_code == 404

    as_user("institution_a")
    res = client.post(f"{API}/evidence-requests/{requests[0]['id']}/fulfil", json={"note": "Letter attached", "document_id": "cert-a"})
    assert res.status_code == 200 and res.json()["status"] == "fulfilled"
    assert fake.rows("applications")[0]["workflow_status"] == "under_review"
    assert next(f for f in fake.rows("findings") if f["id"] == finding["id"])["status"] == "open"
    assert client.post(f"{API}/evidence-requests/{requests[0]['id']}/fulfil", json={"note": "again"}).status_code == 409

    as_user("reviewer")
    reviewer_notes = client.get(f"{API}/notifications").json()
    assert any(n["kind"] == "evidence_fulfilled" for n in reviewer_notes["items"])
    client.post(f"{API}/notifications/read-all")
    assert client.get(f"{API}/notifications").json()["unread"] == 0
    assert any(e["p_type"] == "evidence_request_fulfilled" for e in fake.audit)


def test_queue_orders_by_priority_and_cross_list_is_reviewer_only(fake, client, as_user):
    _submitted_with_unclear_date(fake)
    fake.table("applications").update({"workflow_status": "under_review", "review_deadline": "2026-12-31"}).eq("id", "app-b").execute()
    as_user("reviewer")
    rows = client.get(f"{API}/queue").json()
    assert [r["application"]["code"] for r in rows] == ["INST-1001-2027-28-01", "INST-1002-2027-28-01"]
    top = rows[0]["priority"]
    assert top["score"] == sum(t["contribution"] for t in top["composition"]) and top["composition"]
    assert [r["application"]["code"] for r in client.get(f"{API}/queue?band=Low").json()] == ["INST-1002-2027-28-01"]
    assert client.get(f"{API}/cross").json() == []
    as_user("institution_a")
    assert client.get(f"{API}/queue").status_code == 403
    assert client.get(f"{API}/cross").status_code == 403


def test_replacement_document_triggers_a_system_run_that_auto_closes(fake):
    from services.pipeline import revalidate_after_replacement
    _submitted_with_unclear_date(fake)
    fake.table("extracted_fields").update({"review_state": "auto", "review_reason": None}).eq("id", "f-issue").execute()
    fake.table("extracted_fields").update({"field_value": "2028-03-31"}).eq("id", "f-expiry").execute()
    revalidate_after_replacement(fake.rows("applications")[0])
    assert len(fake.rows("validation_runs")) == 2
    assert [f["status"] for f in fake.rows("findings")] == ["auto_closed"]
    run_event = [e for e in fake.audit if e["p_type"] == "validation_run"][-1]
    assert run_event["p_actor"] is None and run_event["p_detail"]["trigger"] == "document_replaced"


def test_no_system_run_for_a_draft(fake):
    from services.pipeline import revalidate_after_replacement
    revalidate_after_replacement(fake.rows("applications")[0])
    assert fake.rows("validation_runs") == []
