from uuid import UUID
from zipfile import BadZipFile

from docx.opc.exceptions import OpcError
from lxml.etree import XMLSyntaxError

from app.core.storage import DocumentStore
from app.export.docx_export import ExportPendingVerification, InvalidExport
from app.export.learner_reader import render_learner_bundle, render_learner_html


def prepare_learner_download(
    store: DocumentStore, document_id: UUID, offline: bool,
) -> bytes | None:
    """Export a verified working copy as offline reader HTML or a ZIP bundle."""
    with store.locked_session(document_id) as session:
        if session is None:
            return None

        state = store.current_state(session)
        audit = store.read_audit(state)
        if any(finding.status == "fixed_unverified" for finding in audit.findings):
            raise ExportPendingVerification

        contents = (state / "working.docx").read_bytes()
        try:
            export = render_learner_html(contents).encode("utf-8") if offline else render_learner_bundle(contents)
        except (BadZipFile, OpcError, XMLSyntaxError, KeyError, TypeError, AttributeError, RecursionError):
            raise InvalidExport from None
        return export
