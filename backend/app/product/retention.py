import logging
from contextlib import suppress
from datetime import timedelta
from time import time
from uuid import UUID

from sqlalchemy import delete, select

from app.product.db import now
from app.product.security import log_event
from app.product.tables import AccountToken, AuditLog, Document, Invite, ReaderShare, Session, UsageEvent, User


def share_path(state, share):
    return state.shares_root / f"{share.id}.html"


def revoke_share(db, state, share):
    share_path(state, share).unlink(missing_ok=True)
    db.delete(share)


def remove_content(db, state, document, *, shares):
    state.documents.purge(UUID(document.id))
    if shares:
        for share in db.scalars(select(ReaderShare).where(ReaderShare.document_id == document.id)):
            revoke_share(db, state, share)
        # Delete explicit child rows before the database cascades the document deletion.
        db.flush()


def cleanup(state):
    current = now()
    with state.sessions.begin() as db:
        for doc in db.scalars(select(Document).where(Document.history_until <= current)):
            remove_content(db, state, doc, shares=True)
            if doc.status == "active":
                log_event(db, "document_expired", "document", workspace=doc.workspace_id, target=doc.id)
            db.delete(doc)
        for doc in db.scalars(select(Document).where(Document.expires_at <= current, Document.status == "active")):
            remove_content(db, state, doc, shares=False)
            doc.status = "expired"
            log_event(db, "document_expired", "document", workspace=doc.workspace_id, target=doc.id)
        for share in db.scalars(select(ReaderShare).where(ReaderShare.expires_at <= current)):
            revoke_share(db, state, share)
        for model in (Session, AccountToken, Invite):
            db.execute(delete(model).where(model.expires_at <= current))
        db.execute(delete(AuditLog).where(AuditLog.created_at <= current - timedelta(days=state.audit_days)))
        db.execute(delete(UsageEvent).where(UsageEvent.created_at <= current - timedelta(days=62)))
        share_ids = set(db.scalars(select(ReaderShare.id)))
    cutoff = time() - 3600
    for path in state.shares_root.glob("*.html"):
        with suppress(FileNotFoundError):
            if path.stem not in share_ids and path.stat().st_mtime <= cutoff:
                path.unlink()
    state.documents.expire_old_sessions()


def send_expiry_notices(state):
    current = now()
    with state.sessions.begin() as db:
        notices = db.execute(select(Document, User.email).join(User, User.id == Document.uploaded_by).where(
            Document.status == "active", Document.warning_sent.is_(False),
            Document.expires_at > current, Document.expires_at <= current + timedelta(hours=24),
        ).limit(25))
        for doc, email in notices:
            try:
                state.mailer.send(email, "An A11yra upload will expire soon",
                                  f"An uploaded file expires at {doc.expires_at:%Y-%m-%d %H:%M} UTC. "
                                  "Open your workspace to download anything you still need.")
            except (OSError, ValueError, KeyError):
                logging.getLogger("a11yra").warning('{"event":"mail_delivery_failed"}')
            else:
                doc.warning_sent = True
