"""Generate a pair of editable DOCX handouts for accessibility audit tests."""

import argparse
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import nsmap, qn
from docx.shared import Inches, Pt
from docx.text.paragraph import Paragraph
from PIL import Image, ImageDraw

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def attendance_chart() -> BytesIO:
    image = Image.new("RGB", (360, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.line((30, 160, 330, 160), fill="#262522", width=2)
    for x, day, students in [(65, "Monday", 12), (215, "Thursday", 24)]:
        top = 160 - 5 * students
        draw.rectangle((x, top, x + 80, 159), fill="#234d68")
        draw.text((x, top - 18), str(students), fill="#262522")
        draw.text((x, 170), day, fill="#262522")
    stream = BytesIO()
    image.save(stream, format="PNG")
    stream.seek(0)
    return stream


def add_link(paragraph: Paragraph, text: str) -> None:
    url = "https://example.org/study-schedule"
    relationship_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)

    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    properties.append(underline)
    run.append(properties)
    label = OxmlElement("w:t")
    label.text = text
    run.append(label)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def make_handout(path: Path, *, clean: bool) -> None:
    document = Document()
    document.core_properties.title = "Study group handout" if clean else ""

    # The python-docx template already has a default language. Remove it for the broken sample.
    language = document.styles.element.find(
        "w:docDefaults/w:rPrDefault/w:rPr/w:lang", namespaces=nsmap
    )
    if clean:
        language.set(qn("w:val"), "en-US")
    else:
        language.getparent().remove(language)

    if clean:
        document.add_heading("Study group handout", level=1)
    else:
        fake_heading = document.add_paragraph().add_run("Study group handout")
        fake_heading.bold = True
        fake_heading.font.size = Pt(22)

    document.add_paragraph("The chart compares attendance across this week’s study groups.")
    picture = document.add_picture(attendance_chart(), width=Inches(3.75))
    if clean:
        picture._inline.docPr.set(
            "descr", "Study group attendance doubled from 12 students on Monday to 24 on Thursday."
        )

    paragraph = document.add_paragraph("Schedule: ")
    add_link(paragraph, "Weekly study group schedule" if clean else "click here")

    table = document.add_table(rows=3, cols=2)
    table.style = "Table Grid"
    for row, values in zip(table.rows, [("Day", "Room"), ("Monday", "201"), ("Thursday", "103")]):
        for cell, value in zip(row.cells, values):
            cell.text = value
    header = table.rows[0]
    for cell in header.cells:
        cell.paragraphs[0].runs[0].bold = True
    if clean:
        header._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))

    document.save(path)


def make_fixtures(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    broken = output_dir / "broken.docx"
    clean = output_dir / "clean.docx"
    make_handout(broken, clean=False)
    make_handout(clean, clean=True)
    return broken, clean


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=FIXTURE_DIR)
    args = parser.parse_args()
    for path in make_fixtures(args.output_dir):
        print(f"Created {path}")
