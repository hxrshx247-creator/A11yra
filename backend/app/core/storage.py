from contextlib import contextmanager, suppress
from pathlib import Path
from shutil import rmtree
from threading import Lock
from time import time
from uuid import UUID, uuid4

from app.core.config import SESSION_TTL_SECONDS
from app.models import Audit


class DocumentStore:
    def __init__(self, root: Path, ttl_seconds: int = SESSION_TTL_SECONDS) -> None:
        self.root = root
        self.ttl_seconds = ttl_seconds
        self._lock = Lock()

    def save(self, document_id: UUID, contents: bytes, audit: Audit) -> None:
        session = self.root / str(document_id)
        with self._lock:
            session.mkdir(mode=0o700)
            try:
                (session / "original.docx").write_bytes(contents)
                self._write_state(session, contents, audit)
            except OSError:
                rmtree(session, ignore_errors=True)
                raise

    @contextmanager
    def locked_session(self, document_id: UUID):
        session = self.root / str(document_id)
        with self._lock:
            try:
                uploaded_at = (session / "original.docx").stat().st_mtime
            except FileNotFoundError:
                yield None
            else:
                yield session if uploaded_at > time() - self.ttl_seconds else None

    @staticmethod
    def current_state(session: Path) -> Path:
        try:
            state_id = UUID((session / "current").read_text(encoding="ascii"))
        except FileNotFoundError:
            return session
        return session / str(state_id)

    @staticmethod
    def read_audit(state: Path) -> Audit:
        return Audit.model_validate_json((state / "audit.json").read_bytes())

    def load_audit(self, document_id: UUID) -> Audit | None:
        with self.locked_session(document_id) as session:
            return self.read_audit(self.current_state(session)) if session is not None else None

    @staticmethod
    def save_audit(state: Path, audit: Audit) -> None:
        staged = state / "audit.json.tmp"
        staged.write_text(audit.model_dump_json(), encoding="utf-8")
        staged.replace(state / "audit.json")

    @staticmethod
    def _write_state(state: Path, contents: bytes, audit: Audit) -> None:
        (state / "working.docx").write_bytes(contents)
        (state / "audit.json").write_text(audit.model_dump_json(), encoding="utf-8")

    def commit_state(self, session: Path, previous_state: Path, contents: bytes, audit: Audit) -> None:
        # Stage both files before switching the pointer to the new version.
        # The caller holds the session lock, so readers always see one complete pair.
        state = session / str(uuid4())
        state.mkdir(mode=0o700)
        try:
            self._write_state(state, contents, audit)
            pointer = state / "current"
            pointer.write_text(state.name, encoding="ascii")
            pointer.replace(session / "current")
        except OSError:
            rmtree(state, ignore_errors=True)
            raise

        if previous_state == session:
            for filename in ("working.docx", "audit.json"):
                with suppress(OSError):
                    (session / filename).unlink()
        else:
            rmtree(previous_state, ignore_errors=True)

    def expire_old_sessions(self) -> None:
        cutoff = time() - self.ttl_seconds
        with self._lock:
            for session in self.root.iterdir():
                with suppress(OSError):
                    if session.name.startswith("retired-"):
                        rmtree(session)
                    elif (session / "original.docx").stat().st_mtime <= cutoff:
                        rmtree(self.retire_session(session))

    def retire_session(self, session: Path) -> Path:
        # The caller holds the lock. Detach the files from the public session ID.
        return session.rename(self.root / f"retired-{uuid4()}")

    def remove_retired_session(self, session: Path) -> None:
        with self._lock, suppress(OSError):
            # A locked file can be retried by the timeout sweep.
            rmtree(session)

    def delete(self, document_id: UUID) -> bool:
        with self.locked_session(document_id) as session:
            if session is None:
                return False
            retired = self.retire_session(session)
        self.remove_retired_session(retired)
        return True

    def purge(self, document_id: UUID) -> None:
        with self._lock:
            session = self.root / str(document_id)
            if session.is_dir():
                rmtree(session)
