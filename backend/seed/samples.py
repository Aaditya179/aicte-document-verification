"""
Synthetic sample files for trying the upload pipeline by hand (phase 1). Everything is fictional.

Run from backend/ with:  PYTHONPATH=. .venv/bin/python -m seed.samples
Files are written to backend/seed/samples/ (git-ignored):

- application_form.pdf        every application-form field, for the Aarohan application
- approval_certificate.pdf    an ambiguous issue date (03/08/2025), which goes to a reviewer to confirm
- faculty_list.pdf            five faculty lines in the documented format
- lab_photo.jpg               a synthetic lab photo with an EXIF date
- not_really_a_pdf.pdf        a PNG renamed to .pdf, which fails the file check

The full generated dataset (about 30 applications) is built in phase 2.
"""
import io
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "samples"

BANNER = "SYNTHETIC DEMO DOCUMENT - fictional institution, not an AICTE record"


def _pdf(path: Path, title: str, pages: list[list[str]]) -> None:
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text((50, 40), BANNER, fontsize=8, color=(0.4, 0.4, 0.4))
        page.insert_text((50, 80), title, fontsize=16)
        y = 120
        for line in lines:
            page.insert_text((50, y), line, fontsize=11)
            y += 20
    doc.save(path)


def _photo(seed_shift: int = 0) -> Image.Image:
    """A synthetic 'lab': benches, monitors and a window, drawn with plain shapes."""
    img = Image.new("RGB", (1200, 800), (214, 220, 226))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 560, 1200, 800], fill=(150, 140, 128))
    d.rectangle([820, 80, 1120, 360], fill=(190, 215, 235), outline=(90, 90, 90), width=8)
    for i in range(4):
        x = 80 + i * 270 + seed_shift
        d.rectangle([x, 470, x + 220, 520], fill=(110, 82, 60))
        d.rectangle([x + 60, 360, x + 160, 450], fill=(30, 34, 40))
        d.rectangle([x + 100, 450, x + 120, 470], fill=(60, 60, 60))
    return img


def run() -> None:
    OUT.mkdir(exist_ok=True)

    _pdf(OUT / "application_form.pdf", "Application form - extension of approval", [[
        "Institution code: INST-1001",
        "Institution name: Aarohan Institute of Technology",
        "Academic year: 2027-28",
        "Number of faculty: 24",
        "Total built-up area: 5,200 sq m",
        "Approval valid until: 31 March 2028",
        "Fire NOC number: FIRE/PUNE/2026/0412",
        "Survey number: 112/3",
    ]])

    _pdf(OUT / "approval_certificate.pdf", "Approval certificate", [[
        "Certificate number: AICTE-SYN/2025/77810",
        "Institution code: INST-1001",
        "Date of issue: 03/08/2025",
        "Valid until: 31 March 2028",
    ]])

    rows = [
        "Code | Name | Designation | Qualification | Masked ID | Period start | Period end",
        "F-001 | Dr. Asha Rao | Professor | PhD | XXXX-XXXX-4821 | 01/07/2019 |",
        "F-002 | Prof. Vikram S. Joshi | Associate Professor | PhD | XXXX-XXXX-1934 | 15/06/2021 |",
        "F-003 | Ms. Nandini Kale | Assistant Professor | M.Tech | XXXX-XXXX-7702 | 01/08/2023 |",
        "F-004 | Mr. Rohan Deshpande | Assistant Professor | M.Tech | XXXX-XXXX-3310 | 01/08/2023 | 31/05/2026",
        "F-005 | Dr. Imran Shaikh | Professor | PhD | XXXX-XXXX-5567 | 10/01/2018 |",
        "",
        "Total faculty: 22",
    ]
    _pdf(OUT / "faculty_list.pdf", "Faculty list", [rows])

    exif = Image.Exif()
    exif[0x8769] = {36867: "2026:09:14 11:20:05"}  # DateTimeOriginal
    _photo().save(OUT / "lab_photo.jpg", "JPEG", quality=88, exif=exif.tobytes())

    buf = io.BytesIO()
    _photo(seed_shift=12).save(buf, "PNG")
    (OUT / "not_really_a_pdf.pdf").write_bytes(buf.getvalue())

    print(f"Sample files written to {OUT}")


if __name__ == "__main__":
    run()
