"""Render a working DOCX as page images for the audit."""

from base64 import b64encode
from io import BytesIO
from pathlib import Path
import re
from shutil import which
from subprocess import DEVNULL, SubprocessError, run
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from zipfile import ZipFile

from lxml import etree
from docx.oxml.ns import nsmap

MAX_PAGES = 20
_renderer = BoundedSemaphore(1)


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


def render_preview_pages(contents: bytes) -> list[str]:
    office, rasterizer = which("soffice"), which("pdftoppm")
    if not office or not rasterizer or not _renderer.acquire(timeout=15):
        return []
    try:
        if not _can_render_offline(contents):
            return []
        with TemporaryDirectory(prefix="a11yra-preview-") as directory:
            folder = Path(directory)
            source = folder / "document.docx"
            source.write_bytes(contents)
            profile = (folder / "office-profile").as_uri()
            run([office, f"-env:UserInstallation={profile}", "--headless", "--convert-to",
                 "pdf:writer_pdf_Export", "--outdir", directory, str(source)],
                check=True, timeout=20, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
            run([rasterizer, "-l", str(MAX_PAGES + 1), "-scale-to", "1400", "-png",
                 str(folder / "document.pdf"), str(folder / "page")],
                check=True, timeout=12, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
            pages = sorted(folder.glob("page-*.png"), key=lambda path: int(path.stem.split("-")[-1]))
            return ["data:image/png;base64," + b64encode(page.read_bytes()).decode("ascii") for page in pages]
    except (OSError, SubprocessError, etree.XMLSyntaxError):
        return []
    finally:
        _renderer.release()
