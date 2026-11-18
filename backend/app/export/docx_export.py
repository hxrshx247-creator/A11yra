from io import BytesIO
from uuid import UUID
from zipfile import BadZipFile
from zlib import error as CompressionError

from docx import Document
from docx.opc.exceptions import OpcError
from lxml.etree import XMLSyntaxError

from app.core.storage import DocumentStore


class ExportPendingVerification(Exception):
    pass


class InvalidExport(Exception):
    pass


def prepare_docx_export(
    store: DocumentStore, document_id: UUID,
) -> bytes | None:
    """Return the verified working DOCX if it is available and readable."""
    with store.locked_session(document_id) as session:
        if session is None:
            return None

        state = store.current_state(session)
        audit = store.read_audit(state)
        if any(finding.status == "fixed_unverified" for finding in audit.findings):
            raise ExportPendingVerification

        contents = (state / "working.docx").read_bytes()
        try:
            if Document(BytesIO(contents)).element.body is None:
                raise InvalidExport
        except (BadZipFile, CompressionError, OpcError, XMLSyntaxError, KeyError, ValueError,
                TypeError, AttributeError, RecursionError, RuntimeError):
            raise InvalidExport from None
        return contents
