"""
In-memory data store: loads the CSVs, validates them, builds the analytical model.

`reload()` performs a real re-read from disk. If the new files fail to load, the
previously loaded model stays active and the error is reported (never silently
replaced by fabricated data).
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from ..analytics.data_model import AnalyticsModel, build_model
from ..analytics.quality import REQUIRED_COLUMNS, run_validation

log = logging.getLogger("shopsphere.data")

DATASETS = ("orders", "returns", "products", "customers")


class DataUnavailableError(RuntimeError):
    """Raised when no valid dataset has been loaded."""


class DataStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._lock = threading.RLock()
        self._model: AnalyticsModel | None = None
        self.raw: dict[str, pd.DataFrame] = {}
        self.validation: dict | None = None
        self.dataset_info: dict = {}
        self.loaded_at: datetime | None = None
        self.last_error: str | None = None

    # ------------------------------------------------------------------ #
    def load(self) -> dict:
        with self._lock:
            try:
                raw = self._read_files()
                validation = run_validation(raw)
                info = self._read_info()
                snapshot = date.fromisoformat(info["snapshot_date"]) if info.get("snapshot_date") else None
                model = build_model(raw["orders"], raw["returns"], raw["products"], raw["customers"],
                                    snapshot_date=snapshot)
            except Exception as exc:  # keep previous model on failure
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.error("Data load failed: %s", self.last_error)
                raise
            self.raw, self.validation, self.dataset_info, self._model = raw, validation, info, model
            self.loaded_at = datetime.now(timezone.utc)
            self.last_error = None
            summary = validation["summary"]
            log.info("Loaded %s order lines, %s returns from %s (%s errors, %s warnings)",
                     len(raw["orders"]), len(raw["returns"]), self.data_dir, summary["errors"], summary["warnings"])
            return self.status()

    def _read_files(self) -> dict[str, pd.DataFrame]:
        missing = [n for n in DATASETS if not (self.data_dir / f"{n}.csv").exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing dataset file(s) in {self.data_dir}: {', '.join(m + '.csv' for m in missing)}. "
                "Run `python scripts/generate_data.py` from the repository root.")
        frames = {}
        for name in DATASETS:
            df = pd.read_csv(self.data_dir / f"{name}.csv", dtype=str, keep_default_na=False)
            absent = [c for c in REQUIRED_COLUMNS[name] if c not in df.columns]
            if absent:
                raise ValueError(f"{name}.csv is missing required columns: {', '.join(absent)}")
            frames[name] = df
        return frames

    def _read_info(self) -> dict:
        path = self.data_dir / "dataset_info.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("dataset_info.json is not valid JSON; ignoring it")
            return {}

    # ------------------------------------------------------------------ #
    @property
    def model(self) -> AnalyticsModel:
        if self._model is None:
            raise DataUnavailableError(self.last_error or "Data has not been loaded.")
        return self._model

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def status(self) -> dict:
        return {
            "loaded": self.is_loaded,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "data_dir": self.data_dir.name,
            "rows": {k: int(len(v)) for k, v in self.raw.items()},
            "validation": self.validation["summary"] if self.validation else None,
            "error": self.last_error,
        }
