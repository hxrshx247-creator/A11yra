"""Prepare the public lecture's formatted pages during the demo image build."""

from hashlib import sha256
from io import BytesIO
import json
from uuid import uuid4

from docx import Document

from app.audit.runner import run_audit
from app.export.page_preview import BUNDLED_PREVIEW, render_preview_pages


def main() -> None:
    source = BUNDLED_PREVIEW.with_name("stack-queue-lecture.docx").read_bytes()
    findings = run_audit(Document(BytesIO(source)), uuid4()).findings
    pages, positions = render_preview_pages(source, findings)
    if pages and all(finding.id in positions for finding in findings):
        BUNDLED_PREVIEW.write_text(json.dumps({
            "digest": sha256(source).hexdigest(), "pages": pages, "positions": positions,
        }), encoding="utf-8")
    else:
        print("The demo preview will be rendered on request.")


if __name__ == "__main__":
    main()
