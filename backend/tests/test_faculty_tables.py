"""
Faculty lists sent as ordinary PDF tables (services/extraction.py, form 2), read from real PDFs made here.
The "|" lines of the seeded documents still read first and the same.
"""
import pymupdf

from services.extraction import PageText, parse_faculty, read_pages

PDF = "application/pdf"


def table_pdf(pages: list[list[list[str]]], xs: list[float], ruled: bool = False, after: str = "Total faculty: 2",
              leading: float = 24) -> bytes:
    """Each page is a list of lines; each line a list of cells (a cell may hold "\n" for a second line)."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page(width=720, height=600)
        y = 60
        for cells in lines:
            height = leading * max(c.count("\n") + 1 for c in cells) if any("\n" in c for c in cells) else leading
            for x, cell in zip(xs, cells):
                for k, part in enumerate(cell.split("\n")):
                    page.insert_text((x + 3, y + 14 + k * 9), part, fontsize=7)
            if ruled:
                page.draw_line((xs[0], y), (xs[-1] + 80, y))
            y += height
        if ruled:
            page.draw_line((xs[0], y), (xs[-1] + 80, y))
            for x in xs + [xs[-1] + 80]:
                page.draw_line((x, 60), (x, y))
        if after:
            page.insert_text((xs[0], y + 30), after, fontsize=11)
    return doc.tobytes()


def read(data: bytes) -> list[dict]:
    return parse_faculty(read_pages(data, PDF))


INDIAN = ["S.No", "Name of Faculty", "Designation", "Qualification", "Aadhaar No.", "Date of Joining", "Date of Leaving"]
X7 = [50, 90, 210, 330, 400, 480, 550]
ROWS = [["1", "Dr. Asha Rao", "Professor", "Ph.D.", "1234 5678 4821", "01/07/2019", ""],
        ["2", "Mr. Rohan Deshpande", "Assistant Professor", "M.Tech", "9876 5432 3310", "1 August 2023", "31/05/2026"]]


def test_ruled_table_with_the_usual_headings():
    rows = read(table_pdf([[INDIAN] + ROWS], X7, ruled=True))
    assert [(r["faculty_code"], r["name_raw"], r["name_norm"]) for r in rows] == [
        ("F-001", "Dr. Asha Rao", "asha rao"), ("F-002", "Mr. Rohan Deshpande", "rohan deshpande")]
    assert rows[0] == {**rows[0], "designation": "Professor", "qualification": "Ph.D.", "masked_id": "XXXX-XXXX-4821",
                       "period_start": "2019-07-01", "period_end": None, "page_number": 1}
    assert rows[1]["period_start"] == "2023-08-01" and rows[1]["period_end"] == "2026-05-31"


def test_unruled_table_reads_the_same():
    assert read(table_pdf([[INDIAN] + ROWS], X7)) == read(table_pdf([[INDIAN] + ROWS], X7, ruled=True))


def test_full_ids_are_never_stored():
    rows = read(table_pdf([[INDIAN] + ROWS], X7))
    assert all("5678" not in (r["masked_id"] or "") and "1234" not in (r["masked_id"] or "") for r in rows)


def test_other_column_order_with_codes_and_one_period_column():
    head = ["Faculty Code", "Masked ID", "Name", "Qualification", "Designation", "Period"]
    xs = [50, 120, 210, 330, 400, 500]
    data = table_pdf([[head, ["CSE-07", "XXXX-XXXX-1111", "Prof. Kavita Iyer", "PhD", "Professor", "01/07/2019 to present"],
                       ["CSE-09", "XXXX-XXXX-2222", "Ms. Neha Kulkarni", "M.E.", "Lecturer", "02/01/2020 - 30/06/2025"]]], xs)
    rows = read(data)
    assert [(r["faculty_code"], r["masked_id"], r["period_start"], r["period_end"]) for r in rows] == [
        ("CSE-07", "XXXX-XXXX-1111", "2019-07-01", None), ("CSE-09", "XXXX-XXXX-2222", "2020-01-02", "2025-06-30")]


def test_wrapped_heading_and_wrapped_name():
    head = ["S.No", "Name of Faculty", "Designation", "Qualification", "Aadhaar No.", "Date of\nJoining", "Date of\nLeaving"]
    rows_in = [["1", "Dr. Venkata Subramanian\nRaghavan", "Professor", "Ph.D.", "1234 5678 4821", "01/07/2019", ""],
               ["2", "Mr. Rohan Deshpande", "Lecturer", "M.Tech", "9876 5432 3310", "01/08/2023", ""]]
    rows = read(table_pdf([[head] + rows_in], X7, leading=24))
    assert [r["name_raw"] for r in rows] == ["Dr. Venkata Subramanian Raghavan", "Mr. Rohan Deshpande"]
    assert [r["period_start"] for r in rows] == ["2019-07-01", "2023-08-01"]


def test_table_continues_on_the_next_page_without_a_heading():
    page2 = [["3", "Ms. Priya Nair", "Associate Professor", "Ph.D.", "5555 6666 7777", "15/06/2021", ""]]
    rows = read(table_pdf([[INDIAN] + ROWS, page2], X7, after=""))
    assert [(r["faculty_code"], r["name_raw"], r["page_number"]) for r in rows][-1] == ("F-003", "Ms. Priya Nair", 2)
    assert len(rows) == 3


def test_seeded_pipe_lines_in_a_pdf_still_read_first():
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(["Code | Name | Designation | Qualification | Masked ID | Period start | Period end",
                              "F-001 | Dr. Asha Rao | Professor | PhD | XXXX-XXXX-4821 | 01/07/2019 |",
                              "", "Total faculty: 1"]):
        page.insert_text((50, 80 + 20 * i), line, fontsize=11)
    rows = read(doc.tobytes())
    assert [(r["faculty_code"], r["name_norm"], r["masked_id"]) for r in rows] == [("F-001", "asha rao", "XXXX-XXXX-4821")]


def test_ordinary_text_is_not_a_table():
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(["Faculty list", "Name of the institution: Aarohan Institute of Technology",
                              "The faculty named below hold the designation and qualification shown.", "Total faculty: 24"]):
        page.insert_text((50, 80 + 20 * i), line, fontsize=11)
    assert read(doc.tobytes()) == []


def test_pipe_lines_under_a_header_with_numbered_names():
    # As a tester's faculty list reads (29/10/2026): the header names the columns, and each row puts
    # the serial number and the name in one cell
    text = "\n".join([
        "Total Faculty: 2",
        "Format: No. | Name | Designation | Qualification | ID | Period",
        "1. Dr. Meera Kulkarni | Professor | Ph.D. Electronics | FAC-XXXX2101 | 2019-06-01 to present",
        "2. Prof. Rohan Deshpande | Associate Professor | M.Tech. Computer Engineering | FAC-XXXX2102 | 2020-07-15 to 2025-05-31",
        "Generated test data. Not an official document.",
    ])
    rows = parse_faculty([PageText(1, text, "PDF_TEXT", None)])
    assert [(r["faculty_code"], r["name_raw"], r["designation"], r["masked_id"], r["period_start"], r["period_end"]) for r in rows] == [
        ("F-001", "Dr. Meera Kulkarni", "Professor", "FAC-XXXX2101", "2019-06-01", None),
        ("F-002", "Prof. Rohan Deshpande", "Associate Professor", "FAC-XXXX2102", "2020-07-15", "2025-05-31")]
