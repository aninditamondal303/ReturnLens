"""Shared FastAPI dependencies: data store access, global filters, CSV responses."""
from __future__ import annotations

import io
import re
from datetime import date
from typing import Optional

import pandas as pd
from fastapi import Query, Request
from fastapi.responses import StreamingResponse

from ..analytics.data_model import AnalyticsModel
from ..analytics.filters import Filters
from ..services.common import BadRequestError
from ..services.datastore import DataStore


def get_store(request: Request) -> DataStore:
    return request.app.state.store


def get_model(request: Request) -> AnalyticsModel:
    return request.app.state.store.model  # raises DataUnavailableError -> HTTP 503


def get_filters(
    start_date: Optional[date] = Query(None, description="Inclusive order-date lower bound (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Inclusive order-date upper bound (YYYY-MM-DD)"),
    category: Optional[str] = Query(None, description="Category name; comma-separate for several"),
    region: Optional[str] = Query(None, description="Shipping region; comma-separate for several"),
    channel: Optional[str] = Query(None, description="Sales channel; comma-separate for several"),
) -> Filters:
    if start_date and end_date and start_date > end_date:
        raise BadRequestError("start_date must be on or before end_date")
    return Filters(
        start_date=start_date,
        end_date=end_date,
        categories=Filters.parse_list(category),
        regions=Filters.parse_list(region),
        channels=Filters.parse_list(channel),
    )


def csv_response(df: pd.DataFrame, stem: str, f: Filters | None = None) -> StreamingResponse:
    """Serialise a DataFrame as a downloadable CSV whose file name records the active filters."""
    parts = [stem]
    if f is not None:
        if f.start_date or f.end_date:
            parts.append(f"{f.start_date or 'start'}_to_{f.end_date or 'end'}")
        for group in (f.categories, f.regions, f.channels):
            if group:
                parts.append("-".join(group))
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", "_".join(str(p) for p in parts)).strip("-")[:150] + ".csv"
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "X-Row-Count": str(len(df))},
    )
