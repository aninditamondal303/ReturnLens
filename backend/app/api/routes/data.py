"""Data Explorer endpoints: quality report, previews and source CSV downloads."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from ...schemas.responses import DataQualityResponse, DatasetPreviewResponse
from ...services import explorer_service
from ...services.common import NotFoundError
from ...services.datastore import DATASETS, DataStore
from ..deps import get_store

router = APIRouter(tags=["data"])


@router.get("/data-quality", response_model=DataQualityResponse, summary="Validation results, profiles, dictionary")
def data_quality(store: DataStore = Depends(get_store)) -> dict:
    return explorer_service.quality(store)


@router.get("/data/{dataset}", response_model=DatasetPreviewResponse, summary="Searchable, sortable raw data preview")
def preview(
    dataset: str,
    store: DataStore = Depends(get_store),
    search: Optional[str] = Query(None, max_length=100),
    sort_by: Optional[str] = Query(None),
    sort_dir: Literal["asc", "desc"] = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> dict:
    store.model  # noqa: B018 - raises 503 when no data is loaded
    return explorer_service.preview(store, dataset, search, sort_by, sort_dir, page, page_size)


@router.get("/data/{dataset}/download", summary="Download the source CSV file")
def download(dataset: str, store: DataStore = Depends(get_store)):
    if dataset not in DATASETS:
        raise NotFoundError(f"Unknown dataset '{dataset}'. Use one of: {', '.join(DATASETS)}")
    path = store.data_dir / f"{dataset}.csv"
    if not path.exists():
        raise NotFoundError(f"{dataset}.csv is not present in the data folder")
    return FileResponse(path, media_type="text/csv", filename=f"shopsphere_{dataset}.csv")
