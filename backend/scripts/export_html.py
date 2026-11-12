"""Convert an exported DOCX to a standalone semantic HTML preview."""

import argparse
from pathlib import Path

from app.export.html_export import convert_docx_to_html
from app.export.learner_reader import render_learner_bundle, render_learner_html


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("html", type=Path)
    formats = parser.add_mutually_exclusive_group()
    formats.add_argument("--reader", action="store_true", help="Write a single-file learner reader.")
    formats.add_argument("--bundle", action="store_true", help="Write a ZIP with the HTML reader and sibling assets.")
    args = parser.parse_args()
    suffix = ".zip" if args.bundle else ".html"
    if args.docx.suffix.lower() != ".docx" or args.html.suffix.lower() != suffix:
        parser.error(f"Choose a .docx source and a {suffix} output file.")
    if args.bundle:
        args.html.write_bytes(render_learner_bundle(args.docx.read_bytes()))
        return
    render = render_learner_html if args.reader else convert_docx_to_html
    args.html.write_text(render(args.docx.read_bytes()), encoding="utf-8")


if __name__ == "__main__":
    main()
