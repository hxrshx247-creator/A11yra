from io import BytesIO
from pathlib import PureWindowsPath
from zipfile import BadZipFile, ZipFile
from zlib import error as CompressionError

from docx import Document
from docx.document import Document as WordDocument
from docx.opc.exceptions import OpcError
from fastapi import UploadFile
from lxml.etree import XMLSyntaxError

from app.core.config import DOCX_MIME, MAX_EXPANDED_BYTES, MAX_PACKAGE_PARTS, MAX_UPLOAD_BYTES
from app.core.errors import ApiError


def upload_too_large() -> ApiError:
    return ApiError(413, "file_too_large", "Choose a Word document that is 10 MB or smaller.")


def read_docx(upload: UploadFile) -> tuple[str, bytes, WordDocument]:
    # Keep the display name separate from the fixed filenames used on disk.
    filename = PureWindowsPath(upload.filename or "").name
    mime = (upload.content_type or "").partition(";")[0].strip().lower()
    if len(filename) <= len(".docx") or not filename.lower().endswith(".docx") or mime != DOCX_MIME:
        raise ApiError(415, "invalid_file_type", "Choose a Word document with the .docx extension.")

    if upload.size is not None and upload.size > MAX_UPLOAD_BYTES:
        raise upload_too_large()
    contents = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise upload_too_large()

    try:
        if not contents.startswith(b"PK\x03\x04"):
            raise BadZipFile
        with ZipFile(BytesIO(contents)) as package:
            parts = package.infolist()
            names = package.namelist()
            if (
                len(parts) > MAX_PACKAGE_PARTS
                or sum(part.file_size for part in parts) > MAX_EXPANDED_BYTES
                or len(set(names)) != len(names)
                or "word/document.xml" not in names
            ):
                raise BadZipFile

        document = Document(BytesIO(contents))
        if document.element.body is None:
            raise BadZipFile
    except (
        BadZipFile, CompressionError, OpcError, XMLSyntaxError, KeyError, ValueError,
        TypeError, AttributeError, RecursionError, RuntimeError,
    ):
        raise ApiError(422, "corrupt_docx", "Word could not read this file. Save it as a new .docx and try again.") from None

    return filename, contents, document
