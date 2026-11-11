from docx import Document
from docx.oxml import OxmlElement
from lxml.etree import SubElement

from app.audit.images import DECORATIVE_TAG, check_images
from scripts.make_fixtures import attendance_chart


def test_broken_fixture_flags_missing_alt_text(broken_doc):
    check, findings = check_images(broken_doc)
    assert check.result == "issues"
    finding, = findings
    assert finding.locator == {"image_index": 0, "paragraph_index": 2}
    assert finding.fixable == "teacher_approved"


def test_clean_fixture_alt_text_passes(clean_doc):
    check, findings = check_images(clean_doc)
    assert check.result == "passed"
    assert not findings


def test_decorative_marker_must_be_enabled(broken_doc):
    properties = broken_doc.inline_shapes[0]._inline.docPr
    extensions = OxmlElement("a:extLst")
    properties.append(extensions)
    extension = OxmlElement("a:ext")
    extensions.append(extension)
    marker = SubElement(extension, DECORATIVE_TAG)
    properties.set("descr", "   ")
    properties.set("title", "Attendance")

    marker.set("val", "0")
    check, _ = check_images(broken_doc)
    assert check.result == "issues"

    marker.set("val", "1")
    check, findings = check_images(broken_doc)
    assert check.result == "passed"
    assert not findings


def test_anchored_picture_in_table_is_included_after_described_picture(clean_doc):
    run = clean_doc.tables[0].cell(1, 0).paragraphs[0].add_run()
    inline = run.add_picture(attendance_chart())._inline
    anchor = OxmlElement("wp:anchor")
    for child in list(inline):
        anchor.append(child)
    inline.getparent().replace(inline, anchor)

    check, findings = check_images(clean_doc)

    assert check.result == "issues"
    finding, = findings
    assert finding.id == "img-002"
    assert finding.locator["image_index"] == 1


def test_no_pictures_is_not_evaluated():
    check, findings = check_images(Document())
    assert check.result == "not_evaluated"
    assert not findings
