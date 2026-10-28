"""Normalisation, field templates, faculty lines and perceptual hashes (build spec section 17)."""
import io
from datetime import date

from PIL import Image, ImageDraw

from services import extraction, normalise
from services.extraction import PageText


# Names -------------------------------------------------------------------------------------------

def test_name_drops_titles_dots_and_commas():
    assert normalise.name("Dr. Asha  Rao") == "asha rao"
    assert normalise.name("Prof. Vikram S. Joshi") == "vikram s joshi"
    assert normalise.name("MRS. Kale, Nandini") == "kale nandini"


# Dates -------------------------------------------------------------------------------------------

def test_textual_and_iso_dates_are_unambiguous():
    for text in ("31 March 2028", "31st March, 2028", "March 31, 2028", "31-Mar-2028", "2028-03-31", "31/03/2028"):
        parsed = normalise.parse_date(text)
        assert parsed.value == date(2028, 3, 31) and not parsed.ambiguous, text


def test_numeric_date_with_both_parts_twelve_or_less_is_ambiguous():
    parsed = normalise.parse_date("03/08/2027")
    assert parsed.ambiguous
    assert parsed.value == date(2027, 8, 3)        # day first, as in India
    assert parsed.alternative == date(2027, 3, 8)
    assert not normalise.parse_date("05/05/2027").ambiguous


def test_unreadable_date_is_not_guessed():
    result = normalise.normalise("date", "sometime next year")
    assert result.value is None and "could not be read" in result.note


# Numbers and identifiers -------------------------------------------------------------------------

def test_numbers_lose_separators_and_units():
    assert normalise.normalise("number", "5,200 sq m").value == "5200"
    assert normalise.normalise("number", "1,234.50 sqm").value == "1234.5"
    assert normalise.normalise("int", "24").value == "24"
    assert normalise.normalise("int", "24.5").value is None


def test_identifier_key_ignores_separators_and_case():
    assert normalise.identifier_key("112/3") == normalise.identifier_key("112-3") == normalise.identifier_key(" 112 / 3 ")
    assert normalise.identifier_key("inst-1001") == normalise.identifier_key("INST 1001")
    assert normalise.identifier_key("INST-1001") != normalise.identifier_key("INST-1010")


# Templates ---------------------------------------------------------------------------------------

TEMPLATES = [
    {"field_name": "expiry_date", "value_type": "date", "regex": r"^\s*Valid until\s*:\s*(.+?)\s*$", "required": True},
    {"field_name": "issue_date", "value_type": "date", "regex": r"^\s*Date of issue\s*:\s*(.+?)\s*$", "required": True},
    {"field_name": "certificate_no", "value_type": "text", "regex": r"^\s*Certificate (?:no\.?|number)\s*:\s*([A-Z0-9][A-Z0-9/-]*)", "required": False},
]


def test_template_keeps_page_and_original_text():
    pages = [PageText(1, "Cover page only", "PDF_TEXT", None),
             PageText(2, "Valid until: 31 March 2028\nDate of issue: 1 April 2025", "PDF_TEXT", None)]
    rows = {r["field_name"]: r for r in extraction.extract_fields(pages, TEMPLATES)}
    assert rows["expiry_date"]["field_value"] == "2028-03-31"
    assert rows["expiry_date"]["original_value"] == "31 March 2028"
    assert rows["expiry_date"]["page_number"] == 2
    assert rows["expiry_date"]["review_state"] == "auto"
    assert "certificate_no" not in rows                   # optional and absent: no row


def test_low_ocr_confidence_and_ambiguous_dates_need_confirmation():
    pages = [PageText(1, "Valid until: 31 March 2028\nDate of issue: 03/08/2025", "OCR", 0.62)]
    rows = {r["field_name"]: r for r in extraction.extract_fields(pages, TEMPLATES, min_confidence=0.8)}
    assert rows["expiry_date"]["review_state"] == "needs_confirmation"
    assert "62%" in rows["expiry_date"]["review_reason"]
    assert "3 August 2025 or 8 March 2025" in rows["issue_date"]["review_reason"]


def test_unread_scan_explains_why_a_field_is_missing():
    rows = extraction.extract_fields([PageText(1, "", "PDF_TEXT", None, unread_scan=True)], TEMPLATES)
    assert all(r["review_state"] == "needs_confirmation" for r in rows)
    assert "OCR is off" in rows[0]["review_reason"]


# Faculty -----------------------------------------------------------------------------------------

def test_faculty_lines_follow_the_documented_format():
    text = "\n".join([
        "Code | Name | Designation | Qualification | Masked ID | Period start | Period end",
        "F-001 | Dr. Asha Rao | Professor | PhD | XXXX-XXXX-4821 | 01/07/2019 |",
        "F-004 | Mr. Rohan Deshpande | Assistant Professor | M.Tech | XXXX-XXXX-3310 | 01/08/2023 | 31/05/2026",
        "Total faculty: 2",
    ])
    rows = extraction.parse_faculty([PageText(3, text, "PDF_TEXT", None)])
    assert [r["faculty_code"] for r in rows] == ["F-001", "F-004"]
    assert rows[0]["name_norm"] == "asha rao" and rows[0]["period_end"] is None and rows[0]["page_number"] == 3
    assert rows[1]["period_end"] == "2026-05-31"


# File type and photos ----------------------------------------------------------------------------

def test_magic_bytes_decide_the_type():
    assert extraction.sniff_mime(b"%PDF-1.7\n...") == "application/pdf"
    assert extraction.sniff_mime(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert extraction.sniff_mime(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert extraction.sniff_mime(b"MZ\x90\x00") is None


def _scene() -> Image.Image:
    img = Image.new("RGB", (800, 600), (210, 214, 220))
    d = ImageDraw.Draw(img)
    for i in range(5):
        d.rectangle([40 + i * 150, 300, 160 + i * 150, 420], fill=(40 + i * 30, 60, 90))
    d.ellipse([500, 60, 700, 220], fill=(240, 200, 80))
    return img


def _bytes(img: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def test_reencoded_and_resized_copy_keeps_a_close_hash():
    original = extraction.photo_metadata(_bytes(_scene(), "PNG"))["phash"]
    copy = _scene().resize((533, 400))
    reencoded = extraction.photo_metadata(_bytes(copy, "JPEG", quality=55))["phash"]
    assert len(original) == 16
    assert extraction.hamming(original, reencoded) <= 8


def test_a_different_photo_is_far_away():
    other = Image.new("RGB", (800, 600), (30, 30, 30))
    ImageDraw.Draw(other).polygon([(0, 600), (400, 0), (800, 600)], fill=(200, 200, 200))
    a = extraction.photo_metadata(_bytes(_scene(), "PNG"))["phash"]
    b = extraction.photo_metadata(_bytes(other, "PNG"))["phash"]
    assert extraction.hamming(a, b) > 8


def test_exif_date_is_read():
    exif = Image.Exif()
    exif[0x8769] = {36867: "2025:01:20 09:15:00"}
    meta = extraction.photo_metadata(_bytes(_scene(), "JPEG", exif=exif.tobytes()))
    assert meta["taken_at"].startswith("2025-01-20T09:15:00")
