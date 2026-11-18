from docx.document import Document

from app.audit._body import BODY_CONTENT, excerpt, text_runs, visible_text, word_flag
from app.models import Check, CheckResult, Finding


def body_tables(document: Document):
    """Return the tables in the document body."""
    return document.element.body.xpath(f".//w:tbl[{BODY_CONTENT}]")


def table_rows(table):
    """Return the rows belonging to a table."""
    return [
        row for row in table.xpath(f".//w:tr[{BODY_CONTENT}]")
        if row.xpath("ancestor::w:tbl[1]")[0] is table
    ]


def check_tables(document: Document) -> tuple[Check, list[Finding]]:
    """Check whether the first row of each eligible table marks its headers."""
    findings: list[Finding] = []
    table_count = 0
    for table_index, table in enumerate(body_tables(document)):
        rows = table_rows(table)
        if not rows:
            continue

        table_count += 1
        first_row = rows[0]
        if word_flag(first_row, "w:trPr/w:tblHeader"):
            continue

        cells = [
            cell for cell in first_row.xpath(f".//w:tc[{BODY_CONTENT}]")
            if cell.xpath("ancestor::w:tr[1]")[0] is first_row
        ]
        runs = [
            run
            for paragraph in first_row.xpath(f".//w:p[{BODY_CONTENT}]")
            if paragraph.xpath("ancestor::w:tr[1]")[0] is first_row
            for run in text_runs(paragraph)
        ]
        labels = ", ".join(f'“{excerpt(visible_text(cell), 40) or "(blank)"}”' for cell in cells[:6])
        if len(cells) > 6:
            labels += ", …"
        evidence = f"Table {table_index + 1} has {len(rows)} rows. The first row contains {labels or 'no cells'} and has no active header marker."
        if any(word_flag(row, "w:trPr/w:tblHeader") for row in rows[1:]):
            evidence += " A later row is marked, so Word ignores its marker."
        if runs and all(word_flag(run, "w:rPr/w:b") for run in runs):
            evidence += " The first row uses bold text."

        findings.append(Finding(
            id=f"table-{table_index + 1:03d}",
            check_id="tables",
            location=f"Table {table_index + 1}, first row",
            locator={"table_index": table_index},
            evidence=evidence,
            barrier=(f"When readers move through the data in Table {table_index + 1}, their screen reader may not associate "
                     f"the cells with {labels or 'the column labels'}."),
            suggestion=(f"Inspect the flagged first row and confirm that {labels or 'its cells'} label the data underneath. "
                        "If they do, mark the first row as the header. If the labels are elsewhere, move them to the top in Word first."),
            severity="medium" if len(rows) > 1 and len(cells) > 1 else "low",
            confidence="high",
            status="open",
            fixable="teacher_approved",
        ))

    result: CheckResult
    if findings:
        result, summary = "issues", "Some tables have no active header row at the top."
    elif table_count:
        result, summary = "passed", "The tables checked have a marked first header row."
    else:
        result, summary = "not_evaluated", "No tables with rows found in the main document."
    return Check(
        id="tables", label="Table headers", result=result, summary=summary,
        finding_ids=[finding.id for finding in findings],
    ), findings
