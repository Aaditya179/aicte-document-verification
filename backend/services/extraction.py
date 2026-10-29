"""
Reading a document (build spec section 6, steps 4 to 7). Plain Python only: nothing here uses an LLM.

Text: PyMuPDF reads each PDF page's text layer. A page with fewer than 20 characters is a scan; when
OCR is on and Tesseract is installed it is rendered at 200 dpi and read by Tesseract, which also gives
an average word confidence (0 to 1). PDF text has no confidence (null). Images go straight to OCR.

Fields: each extraction template is a regex for one field of one document type, applied page by page.
The first match wins and keeps its page number. A value is sent to a reviewer to confirm
(`needs_confirmation`) when a required field is not found, when OCR confidence is below the R-OCR-01
threshold, when the text cannot be read as its type, or when a date is ambiguous.

Faculty lists, in either of two forms:

1. One faculty member per line, fields separated by "|" (the seeded documents):

    code | name | designation | qualification | masked ID | period start | period end

    F-001 | Dr. Asha Rao | Assistant Professor | PhD | XXXX-XXXX-1234 | 01/07/2024 |

   Lines that do not start with a faculty code (the header, the total) are ignored.

2. A table in a PDF, ruled or not, as institutions usually send it. The header row is found by its
   column names (name, designation, qualification, ID, date of joining, date of leaving, serial
   number or code; at least a name and two others) and each word is placed in the column it sits
   under, using the word positions PyMuPDF gives. A row that wraps onto a second line is joined to
   the row above. A table that runs onto the next page without a header keeps the columns found.
   With no code column, the code is F- and the serial number (or the row's position).

An empty period end (or "present", "till date") means the person is still employed. An ID with eight
or more digits is masked to its last four (XXXX-XXXX-1234) before it is stored. Scanned or photographed
lists are read as text by OCR, which keeps no word positions, so only the first form is read from them.

Photos: a 64-bit perceptual hash (imagehash.phash, stored as 16 hex characters), the size, and the
EXIF timestamp and GPS position when present.
"""
import io
import re
import shutil
from dataclasses import dataclass, field
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
    words: list = field(default_factory=list)  # PDF text: (x0, y0, x1, y1, word, ...) from PyMuPDF, for tables


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
                    pages.append(PageText(index, text, "PDF_TEXT", None, words=page.get_text("words")))
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


def _faculty_row(code: str, name: str, designation: str, qualification: str, masked_id: str,
                 start: str, end: str, page: int) -> dict:
    begun, ended = _period_date(start), _period_date(end)
    return {
        "faculty_code": code, "name_raw": name, "name_norm": normalise.name(name),
        "designation": designation or None, "qualification": qualification or None,
        "masked_id": _mask_id(masked_id), "page_number": page,
        "period_start": begun.isoformat() if begun else None,
        "period_end": ended.isoformat() if ended else None,
    }


def _pipe_rows(pages: list[PageText]) -> list[dict]:
    rows = []
    for page in pages:
        for line in page.text.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 6 or not FACULTY_CODE.match(parts[0]):
                continue
            parts += [""] * (7 - len(parts))
            rows.append(_faculty_row(*parts[:7], page=page.page))
    return rows


# Column roles in a faculty table, matched against header cells in this order (the first match wins)
COLUMN_ROLES = [
    ("serial", r"^(?:s\.?\s*no|sr\.?\s*no|sl\.?\s*no|serial(?: no)?|no\.?|#)\.?$"),
    ("masked_id", r"aadhaa?r|\bpan\b|masked|\bid\b|identity|\buid\b"),
    ("code", r"\bcode\b|emp(?:loyee)?\.?\s*(?:no|id|code)|faculty\s*(?:no|id)"),
    ("name", r"\bname\b"),
    ("designation", r"designation|\bpost\b|position|\brank\b"),
    ("qualification", r"qualification|degree"),
    ("start", r"joining|\bdoj\b|period\s*start|^from$|\bstart|joined|appointment"),
    ("end", r"leaving|relieving|\bdol\b|period\s*end|^to$|^till$|\bend\b|resign"),
    ("period", r"^period$|tenure|duration"),
]
ONGOING = {"", "-", "–", "—", "present", "till date", "to date", "till now", "continuing", "current", "now", "working", "ongoing"}


def _role(header: str) -> Optional[str]:
    h = normalise.text(header).lower()
    return next((role for role, pattern in COLUMN_ROLES if re.search(pattern, h)), None)


def _period_date(value: str):
    v = normalise.text(value or "")
    return None if v.lower() in ONGOING else normalise.parse_date(v).value


def _mask_id(value: str) -> Optional[str]:
    """Only the last four digits of a long ID are kept; an ID already masked is kept as it is."""
    v = normalise.text(value or "")
    digits = re.sub(r"\D", "", v)
    if len(digits) >= 8 and "x" not in v.lower():
        return f"XXXX-XXXX-{digits[-4:]}"
    return v or None


def _lines(words: list) -> list[list[tuple]]:
    """Words grouped into lines by their vertical position, each line left to right."""
    lines: list[list[tuple]] = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        middle, height = (w[1] + w[3]) / 2, w[3] - w[1]
        if lines and abs(middle - lines[-1][0][5]) <= max(2.0, height * 0.4):
            lines[-1].append((*w[:5], lines[-1][0][5]))
        else:
            lines.append([(*w[:5], middle)])
    return [sorted(line, key=lambda w: w[0]) for line in lines]


def _cells(line: list[tuple]) -> list[tuple[float, float, str]]:
    """Neighbouring words joined into cells; a gap wider than about a character's height starts a new cell."""
    cells: list[list] = []
    for x0, y0, x1, y1, word, _ in line:
        if cells and x0 - cells[-1][1] <= (y1 - y0) * 0.8:
            cells[-1][1], cells[-1][2] = x1, f"{cells[-1][2]} {word}"
        else:
            cells.append([x0, x1, word])
    return [tuple(c) for c in cells]


def _header(line: list[tuple]) -> Optional[list[tuple[float, str]]]:
    """(left edge, role) of each column if this line is a faculty table header: a name column and two others."""
    columns = [(x0, x1, _role(text)) for x0, x1, text in _cells(sorted(line, key=lambda w: w[0]))]
    roles = [r for _, _, r in columns if r]
    if "name" not in roles or len(set(roles)) < 3:
        return None
    # A column starts halfway between the end of the header before it and its own header
    return [((columns[i - 1][1] + x0) / 2 if i else float("-inf"), role) for i, (x0, _, role) in enumerate(columns)]


def _split(line: list[tuple], columns: list[tuple[float, str]]) -> dict[str, str]:
    out: dict[str, list[str]] = {}
    for x0, _, x1, _, word, _ in line:
        index = max(i for i, (left, _) in enumerate(columns) if left <= (x0 + x1) / 2 or i == 0)
        role = columns[index][1]
        if role:
            out.setdefault(role, []).append(word)
    return {role: " ".join(words) for role, words in out.items()}


def _is_member(cells: dict[str, str]) -> bool:
    """A row about a person: a name that is not a label ("Total faculty: 24"), and a serial number, a code,
    a date of joining or a designation beside it."""
    name = cells.get("name", "")
    if not name or ":" in name or not re.search(r"[A-Za-z]", name):
        return False
    return bool(re.fullmatch(r"\d+\.?", cells.get("serial", "")) or FACULTY_CODE.match(cells.get("code", "").replace(" ", ""))
                or _period_date(cells.get("start", "")) or cells.get("designation"))


def _table_rows(pages: list[PageText]) -> list[dict]:
    rows: list[dict] = []
    columns = None
    for page in pages:
        previous_bottom = header = header_bottom = None
        for line in _lines(page.words):
            top, bottom = min(w[1] for w in line), max(w[3] for w in line)
            found = _header(line)
            if found:
                columns, header, header_bottom, previous_bottom = found, line, bottom, None
                continue
            if not columns:
                continue
            cells = _split(line, columns)
            if header and top - header_bottom < (bottom - top) * 1.2 and not _is_member(cells):
                header = header + line                       # a header that wraps ("Date of" / "Joining")
                columns, header_bottom = _header(header) or columns, bottom
                continue
            header = None
            wrapped = rows and previous_bottom is not None and top - previous_bottom < (bottom - top) * 1.2
            if _is_member(cells):
                rows.append({**cells, "_page": page.page})
                previous_bottom = bottom
            elif wrapped and set(cells) <= {"name", "designation", "qualification"}:
                for role, text in cells.items():             # the rest of a cell that wrapped onto a second line
                    rows[-1][role] = f"{rows[-1].get(role, '')} {text}".strip()
                previous_bottom = bottom
            else:
                previous_bottom = None                      # the table has ended (a total, a note)
    return _members(rows)


def _members(rows: list[dict]) -> list[dict]:
    """Faculty rows from table rows keyed by column role (plus "_page")."""
    out, seen = [], set()
    for i, r in enumerate(rows, start=1):
        start, end = r.get("start", ""), r.get("end", "")
        if r.get("period") and not start:
            parts = re.split(r"\s+(?:to|-|–|—)\s+", r["period"], maxsplit=1)
            start, end = parts[0], parts[1] if len(parts) > 1 else ""
        code = r.get("code", "").replace(" ", "")
        if not FACULTY_CODE.match(code):
            serial = re.sub(r"\D", "", r.get("serial", ""))
            code = f"F-{int(serial or i):03d}"
        while code in seen:
            code += "b"
        seen.add(code)
        out.append(_faculty_row(code, r["name"], r.get("designation", ""), r.get("qualification", ""),
                                r.get("masked_id", ""), start, end, r["_page"]))
    return out


def _headed_pipe_rows(pages: list[PageText]) -> list[dict]:
    """"|" lines under a "|" header that names the columns ("No. | Name | Designation | ..."), in any
    order. A row that puts the serial number and the name in one cell ("1. Dr. Meera Kulkarni | ...")
    is split, so it lines up with the header."""
    rows, roles = [], None
    for page in pages:
        for line in page.text.splitlines():
            if line.count("|") < 2:
                continue
            cells = [c.strip() for c in line.split("|")]
            # "Format: No." or "Columns: Name": the column name is after the colon
            found = [_role(c.split(":")[-1]) for c in cells]
            if "name" in found and len({r for r in found if r}) >= 3:
                roles = found
                continue
            if not roles:
                continue
            numbered = re.match(r"^(\d+)[.)]\s+(.+)$", cells[0])
            if len(cells) == len(roles) - 1 and roles[0] == "serial" and numbered:
                cells = [numbered[1], numbered[2]] + cells[1:]
            row = {role: cell for role, cell in zip(roles, cells) if role and cell}
            if _is_member(row):
                rows.append({**row, "_page": page.page})
    return _members(rows)


def parse_faculty(pages: list[PageText]) -> list[dict]:
    """Rows for proofpath.faculty (without application, institution and document ids): the seeded "|"
    lines, else "|" lines under a header naming the columns, else a table found from word positions."""
    return _pipe_rows(pages) or _headed_pipe_rows(pages) or _table_rows(pages)


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
