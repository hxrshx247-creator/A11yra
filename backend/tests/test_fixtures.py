from docx.oxml.ns import qn


def test_handouts_exercise_the_remaining_four_checks(broken_doc, clean_doc):
    fake_heading = broken_doc.paragraphs[0]
    assert fake_heading.style.name == "Normal"
    assert fake_heading.runs[0].bold
    assert fake_heading.runs[0].font.size.pt == 22
    assert clean_doc.paragraphs[0].style.name == "Heading 1"

    assert broken_doc.inline_shapes[0]._inline.docPr.get("descr") is None
    assert clean_doc.inline_shapes[0]._inline.docPr.get("descr")

    broken_link = broken_doc.paragraphs[-1].hyperlinks[0]
    clean_link = clean_doc.paragraphs[-1].hyperlinks[0]
    assert broken_link.url == clean_link.url == "https://example.org/study-schedule"
    assert broken_link.text == "click here"
    assert clean_link.text == "Weekly study group schedule"

    broken_header = broken_doc.tables[0].rows[0]
    assert all(cell.paragraphs[0].runs[0].bold for cell in broken_header.cells)
    assert broken_header._tr.find(".//" + qn("w:tblHeader")) is None
    assert clean_doc.tables[0].rows[0]._tr.find(".//" + qn("w:tblHeader")) is not None
