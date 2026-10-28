"""
Reading a document (build spec section 6, steps 4 to 7). Plain Python only: nothing here uses an LLM.

Text: PyMuPDF reads each PDF page's text layer. A page with fewer than 20 characters is a scan; when
OCR is on and Tesseract is installed it is rendered at 200 dpi and read by Tesseract, which also gives
an average word confidence (0 to 1). PDF text has no confidence (null). Images go straight to OCR.

Fields: each extraction template is a regex for one field of one document type, applied page by page.
The first match wins and keeps its page number. A value is sent to a reviewer to confirm
(`needs_confirmation`) when a required field is not found, when OCR confidence is below the R-OCR-01
threshold, when the text cannot be read as its type, or when a date is ambiguous.

Faculty lists: one faculty member per line, fields separated by "|":

    code | name | designation | qualification | masked ID | period start | period end

    F-001 | Dr. Asha Rao | Assistant Professor | PhD | XXXX-XXXX-1234 | 01/07/2024 |

An empty period end means the person is still employed. Lines that do not start with a faculty code
(the header, the total) are ignored.

Photos: a 64-bit perceptual hash (imagehash.phash, stored as 16 hex characters), the size, and the
EXIF timestamp and GPS position when present.
"""
import io
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pymupdf
import imagehash
from PIL import ExifTags, Image

from core.config import settings
from services import normalise

MIN_TEXT_CHARS = 20
OCR_DPI = 200
DEFAULT_MIN_CONFIDENCE = 0.80

MIME_PDF = "application/pdf"
MIME_JPEG = "image/jpeg"
MIME_PNG = "image/png"
ALLOWED_MIME = {MIME_PDF, MIME_JPEG, MIME_PNG}
EXTENSIONS = {".pdf": MIME_PDF, ".jpg": MIME_JPEG, ".jpeg": MIME_JPEG, ".png": MIME_PNG}


@dataclass
class PageText:
    page: int                      # 1-based
    text: str
    method: str                    # PDF_TEXT or OCR
    confidence: Optional[float]    # OCR only
    unread_scan: bool = False      # a scanned page left unread because OCR is off or not installed


class UnreadableFile(Exception):
    """The file is not what it claims to be, or cannot be opened."""


# ------------------------------------------------------------------------------------------------
# File checks
# ------------------------------------------------------------------------------------------------

def sniff_mime(data: bytes) -> Optional[str]:
    """The type the file's first bytes show, whatever its name says."""
    if data.startswith(b"%PDF-"):
        return MIME_PDF
    if data.startswith(b"\xff\xd8\xff"):
        return MIME_JPEG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return MIME_PNG
    return None


def page_count(data: bytes, mime: str) -> int:
    if mime != MIME_PDF:
        return 1
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise UnreadableFile("The PDF is password-protected")
            return pdf.page_count
    except UnreadableFile:
        raise
    except Exception as exc:
        raise UnreadableFile("The PDF could not be opened") from exc


# ------------------------------------------------------------------------------------------------
# Text
# ------------------------------------------------------------------------------------------------

def ocr_available() -> bool:
    return settings.OCR_ENABLED and shutil.which("tesseract") is not None


def ocr_image(image: Image.Image) -> tuple[str, Optional[float]]:
    """Text and average word confidence (0 to 1) of an image, line breaks kept."""
    import pytesseract

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    lines: dict[tuple, list[str]] = {}
    confidences = []
    for i, word in enumerate(data["text"]):
        conf = float(data["conf"][i])
        if not word.strip() or conf < 0:
            continue
        lines.setdefault((data["block_num"][i], data["par_num"][i], data["line_num"][i]), []).append(word)
        confidences.append(conf)
    text = "\n".join(" ".join(words) for words in lines.values())
    return text, (round(sum(confidences) / len(confidences) / 100, 3) if confidences else None)


def read_pages(data: bytes, mime: str) -> list[PageText]:
    if mime == MIME_PDF:
        pages = []
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            for index, page in enumerate(pdf, start=1):
                text = page.get_text()
                if len(text.strip()) >= MIN_TEXT_CHARS:
                    pages.append(PageText(index, text, "PDF_TEXT", None))
                elif ocr_available():
                    pix = page.get_pixmap(dpi=OCR_DPI)
                    pages.append(_ocr_page(index, Image.open(io.BytesIO(pix.tobytes("png")))))
                else:
                    pages.append(PageText(index, text, "PDF_TEXT", None, unread_scan=True))
        return pages
    if ocr_available():
        return [_ocr_page(1, Image.open(io.BytesIO(data)))]
    return [PageText(1, "", "OCR", None, unread_scan=True)]


def _ocr_page(index: int, image: Image.Image) -> PageText:
    text, confidence = ocr_image(image)
    return PageText(index, text, "OCR", confidence)


# ------------------------------------------------------------------------------------------------
# Fields
# ------------------------------------------------------------------------------------------------

def extract_fields(pages: list[PageText], templates: list[dict], min_confidence: float = DEFAULT_MIN_CONFIDENCE) -> list[dict]:
    """Rows for proofpath.extracted_fields (without document_id), one per matched or missing required field."""
    rows = []
    unread = [p.page for p in pages if p.unread_scan]
    not_found = "Not found in the document"
    if unread:
        not_found += f"; page {', '.join(map(str, unread))} is a scan and OCR is off, so it was not read"
    for template in templates:
        pattern = re.compile(template["regex"], re.IGNORECASE | re.MULTILINE)
        found = None
        for page in pages:
            match = pattern.search(page.text)
            if match:
                found = (page, match.group(template.get("group_index") or 1))
                break

        if not found:
            if template.get("required"):
                rows.append({
                    "field_name": template["field_name"], "field_value": None, "original_value": None,
                    "value_type": template["value_type"], "page_number": None, "source_method": None,
                    "confidence": None, "review_state": "needs_confirmation",
                    "review_reason": not_found,
                })
            continue

        page, raw = found
        result = normalise.normalise(template["value_type"], raw)
        reasons = []
        if result.value is None or result.ambiguous:
            reasons.append(result.note)
        if page.method == "OCR" and (page.confidence is None or page.confidence < min_confidence):
            shown = "unknown" if page.confidence is None else f"{page.confidence:.0%}"
            reasons.append(f"Read by OCR with {shown} confidence, below {min_confidence:.0%}")
        rows.append({
            "field_name": template["field_name"], "field_value": result.value,
            "original_value": normalise.text(raw), "value_type": template["value_type"],
            "page_number": page.page, "source_method": page.method, "confidence": page.confidence,
            "review_state": "needs_confirmation" if reasons else "auto",
            "review_reason": "; ".join(reasons) or None,
        })
    return rows


FACULTY_CODE = re.compile(r"^[A-Z]{1,4}-?\d+$")


def parse_faculty(pages: list[PageText]) -> list[dict]:
    """Rows for proofpath.faculty (without application, institution and document ids)."""
    rows = []
    for page in pages:
        for line in page.text.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 6 or not FACULTY_CODE.match(parts[0]):
                continue
            parts += [""] * (7 - len(parts))
            start = normalise.parse_date(parts[5]).value if parts[5] else None
            end = normalise.parse_date(parts[6]).value if parts[6] else None
            rows.append({
                "faculty_code": parts[0], "name_raw": parts[1], "name_norm": normalise.name(parts[1]),
                "designation": parts[2] or None, "qualification": parts[3] or None,
                "masked_id": parts[4] or None, "page_number": page.page,
                "period_start": start.isoformat() if start else None,
                "period_end": end.isoformat() if end else None,
            })
    return rows


# ------------------------------------------------------------------------------------------------
# Photos
# ------------------------------------------------------------------------------------------------

EXIF_IFD = 0x8769
GPS_IFD = 0x8825
TAG_DATETIME = 306
TAG_DATETIME_ORIGINAL = 36867


def phash(image: Image.Image) -> str:
    return str(imagehash.phash(image, hash_size=8))


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _exif_datetime(value) -> Optional[datetime]:
    try:
        return datetime.strptime(str(value).strip(), "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _gps_degrees(dms, ref) -> Optional[float]:
    try:
        d, m, s = (float(x) for x in dms)
    except (TypeError, ValueError):
        return None
    value = d + m / 60 + s / 3600
    return round(-value if str(ref).upper() in ("S", "W") else value, 6)


def photo_metadata(data: bytes) -> dict:
    """Fields for proofpath.media_assets: phash, size, EXIF, when it was taken and where."""
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise UnreadableFile("The image could not be opened") from exc

    exif = image.getexif()
    sub = exif.get_ifd(EXIF_IFD)
    gps_raw = exif.get_ifd(GPS_IFD)
    taken = _exif_datetime(sub.get(TAG_DATETIME_ORIGINAL) or exif.get(TAG_DATETIME) or "")

    gps = None
    if gps_raw.get(2) and gps_raw.get(4):
        lat, lon = _gps_degrees(gps_raw.get(2), gps_raw.get(1)), _gps_degrees(gps_raw.get(4), gps_raw.get(3))
        if lat is not None and lon is not None:
            gps = {"lat": lat, "lon": lon}

    readable = {}
    for tag, value in list(exif.items()) + list(sub.items()):
        name = ExifTags.TAGS.get(tag)
        if name and isinstance(value, (str, int, float)) and name not in ("MakerNote", "UserComment"):
            readable[name] = value if not isinstance(value, str) else value.strip("\x00 ")[:200]

    return {
        "phash": phash(image.convert("RGB")),
        "width": image.width, "height": image.height,
        "exif": readable or None,
        "taken_at": taken.isoformat() if taken else None,
        "gps": gps,
    }
