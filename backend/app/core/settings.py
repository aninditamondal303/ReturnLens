"""Runtime settings read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader (KEY=VALUE lines) so no extra dependency is needed."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(REPO_ROOT / ".env")
_load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = Path(os.environ.get("SHOPSPHERE_DATA_DIR") or REPO_ROOT / "data").resolve()
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "SHOPSPHERE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
LOG_LEVEL = os.environ.get("SHOPSPHERE_LOG_LEVEL", "INFO").upper()
APP_VERSION = "1.0.0"
