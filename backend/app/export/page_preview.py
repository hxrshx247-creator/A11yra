"""Render a working DOCX as page images for the audit."""

from base64 import b64encode
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from shutil import which
from subprocess import DEVNULL, PIPE, SubprocessError, run
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from zipfile import ZipFile
from uuid import uuid4

from docx import Document
from lxml import etree
from docx.oxml.ns import nsmap

from app.export.preview_flags import insert_preview_flags
from app.models import Finding

MAX_PAGES = 20
_renderer = BoundedSemaphore(1)
BUNDLED_PREVIEW = Path(__file__).resolve().parents[2] / "fixtures" / "stack-queue-preview.json"


@lru_cache(maxsize=1)
def _read_bundled_preview() -> dict:
    return json.loads(BUNDLED_PREVIEW.read_bytes()) if BUNDLED_PREVIEW.is_file() else {}


def bundled_preview(contents: bytes, flags: list[Finding] | None) -> tuple[list[str], dict] | None:
    """Return pre-rendered pages when the document matches the bundled sample."""
    # Only the public demo fixture is eligible for the shared preview.
    preview = _read_bundled_preview()
    if sha256(contents).hexdigest() != preview.get("digest"):
        return None
    wanted = {finding.id for finding in flags or []}
    positions = preview["positions"]
    if wanted - positions.keys():
        return None
    return preview["pages"], {key: positions[key] for key in wanted}


def _can_render_offline(contents: bytes) -> bool:
    with ZipFile(BytesIO(contents)) as package:
        for name in package.namelist():
            if name.endswith(".rels"):
                for rel in etree.fromstring(package.read(name)):
                    if rel.get("TargetMode") == "External" and not rel.get("Type", "").endswith("/hyperlink"):
                        return False
            elif name.startswith("word/") and name.endswith(".xml"):
                root = etree.fromstring(package.read(name))
                instructions = "".join(root.xpath("//w:instrText/text()", namespaces=nsmap))
                instructions += " " + " ".join(root.xpath("//w:fldSimple/@w:instr", namespaces=nsmap))
                if re.search(r"\b(?:INCLUDETEXT|INCLUDEPICTURE|DDEAUTO|DDE|LINK)\b", instructions, re.I):
                    return False
    return True


def _flag_positions(pdf: Path, findings: list[Finding], prefix: str) -> dict:
    info = which("pdfinfo")
    if not info:
        return {}
    try:
        boxes = run([info, "-f", "1", "-l", str(MAX_PAGES + 1), "-box", str(pdf)],
                    check=True, timeout=5, stdout=PIPE, stderr=DEVNULL).stdout.decode("ascii", errors="replace")
        anchors = run([info, "-dests", str(pdf)], check=True, timeout=5,
                      stdout=PIPE, stderr=DEVNULL).stdout.decode("ascii", errors="replace")
    except (OSError, SubprocessError):
        return {}
    sizes = {int(page): (float(width), float(height)) for page, width, height in
             re.findall(r"Page\s+(\d+) size:\s+([\d.]+) x ([\d.]+) pts", boxes)}
    positions = {finding.id: {"page": 1, "x": 4.0 + 4 * index, "y": 2.0}
                 for index, finding in enumerate(f for f in findings if "property" in f.locator)}
    for page, x, y, index in re.findall(
        rf'(?m)^\s*(\d+)\s+\[\s*XYZ\s+(-?[\d.]+)\s+(-?[\d.]+)\s+[^\]]+\]\s+"{prefix}-(\d+)"\s*$', anchors
    ):
        page, index = int(page), int(index)
        if page > MAX_PAGES or page not in sizes or index >= len(findings):
            continue
        width, height = sizes[page]
        if width > 0 and height > 0:
            positions[findings[index].id] = {
                "page": page, "x": min(98, max(2, 100 * float(x) / width)),
                "y": min(98, max(2, 100 * (1 - float(y) / height))),
            }
    return positions


def render_preview_pages(contents: bytes, flags: list[Finding] | None = None) -> tuple[list[str], dict]:
    """Render Word preview pages and locate audit flags on them."""
    office, rasterizer = which("soffice"), which("pdftoppm")
    if not office or not rasterizer or not _renderer.acquire(timeout=15):
        return [], {}
    try:
        if not _can_render_offline(contents):
            return [], {}
        with TemporaryDirectory(prefix="a11yra-preview-") as directory:
            folder = Path(directory)
            source = folder / "document.docx"
            output_filter = "pdf:writer_pdf_Export"
            marker = f"a11yra{uuid4().hex[:20]}"
            if flags:
                document = Document(BytesIO(contents))
                insert_preview_flags(document, flags, marker)
                document.save(source)
                output_filter += ':{"ExportBookmarksToPDFDestination":{"type":"boolean","value":"true"}}'
            else:
                source.write_bytes(contents)
            profile = (folder / "office-profile").as_uri()
            run([office, f"-env:UserInstallation={profile}", "--headless", "--convert-to",
                 output_filter, "--outdir", directory, str(source)],
                check=True, timeout=20, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
            pdf = folder / "document.pdf"
            run([rasterizer, "-l", str(MAX_PAGES + 1), "-scale-to", "1200", "-png",
                 str(pdf), str(folder / "page")],
                check=True, timeout=12, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
            pages = sorted(folder.glob("page-*.png"), key=lambda path: int(path.stem.split("-")[-1]))
            images = ["data:image/png;base64," + b64encode(page.read_bytes()).decode("ascii") for page in pages]
            return images, _flag_positions(pdf, flags, marker) if flags else {}
    except (OSError, SubprocessError, etree.XMLSyntaxError):
        return [], {}
    finally:
        _renderer.release()
