from pathlib import Path
from tempfile import gettempdir

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_UPLOAD_BYTES = 10_000_000
MAX_MULTIPART_BYTES = MAX_UPLOAD_BYTES + 64 * 1024
MAX_EXPANDED_BYTES = 100_000_000
MAX_PACKAGE_PARTS = 2_000
SESSION_TTL_SECONDS = 24 * 60 * 60
SESSION_SWEEP_SECONDS = 15
TEMP_ROOT = Path(gettempdir())
