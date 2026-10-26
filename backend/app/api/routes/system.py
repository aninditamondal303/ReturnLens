"""Health, metadata, metric dictionary and data reload."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...analytics import config
from ...analytics.definitions import METRICS
from ...core.settings import APP_VERSION
from ...schemas.responses import HealthResponse, MetadataResponse, MetricDefinition, ReloadResponse
from ...services.datastore import DataStore
from ..deps import get_store

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Service and data health")
def health(store: DataStore = Depends(get_store)) -> dict:
    st = store.status()
    errors = st["validation"]["errors"] if st["validation"] else None
    status = "unavailable" if not st["loaded"] else ("degraded" if errors else "ok")
    return {"status": status, "version": APP_VERSION, "data_loaded": st["loaded"], "loaded_at": st["loaded_at"],
            "rows": st["rows"], "validation_errors": errors, "error": st["error"]}


@router.get("/metadata", response_model=MetadataResponse, summary="Filter options and dataset facts")
def metadata(store: DataStore = Depends(get_store)) -> dict:
    m = store.model
    lines = m.lines
    st = store.status()
    return {
        "app": "ShopSphere | Return Intelligence Lab",
        "version": APP_VERSION,
        "synthetic_data_notice": "All data is synthetic and generated for a fictional company. Results are illustrative.",
        "period_start": m.period_start.isoformat(),
        "period_end": m.period_end.isoformat(),
        "snapshot_date": m.snapshot_date.isoformat(),
        "months": sorted(lines["month"].unique().tolist()),
        "categories": sorted(m.products["category"].unique().tolist()),
        "regions": sorted(lines["shipping_region"].unique().tolist()),
        "channels": sorted(lines["sales_channel"].unique().tolist()),
        "loaded_at": st["loaded_at"],
        "rows": st["rows"],
        "return_rate_target": config.RETURN_RATE_TARGET,
        "risk_thresholds": {"medium": config.MEDIUM_THRESHOLD, "high": config.HIGH_THRESHOLD},
        "validation": st["validation"],
    }


@router.get("/metrics-dictionary", response_model=list[MetricDefinition], summary="Every KPI definition and formula")
def metrics_dictionary() -> list[dict]:
    return METRICS


@router.post("/data/reload", response_model=ReloadResponse, summary="Re-read the CSV files from disk")
def reload_data(store: DataStore = Depends(get_store)) -> dict:
    """Performs a real reload. On failure the previously loaded data stays active and the error is returned."""
    try:
        st = store.load()
        return {"reloaded": True, "message": "CSV files re-read from disk and all metrics rebuilt.",
                "loaded_at": st["loaded_at"], "rows": st["rows"], "validation": st["validation"]}
    except Exception as exc:  # noqa: BLE001 - reported to the user, previous data kept
        st = store.status()
        return {"reloaded": False,
                "message": f"Reload failed; previously loaded data is still active. Reason: {exc}",
                "loaded_at": st["loaded_at"], "rows": st["rows"], "validation": st["validation"]}
