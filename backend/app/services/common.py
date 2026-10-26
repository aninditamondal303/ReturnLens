"""Shared helpers for the page services: metadata envelope, paging, sorting, banding."""
from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..analytics.data_model import AnalyticsModel
from ..analytics.filters import Filters
from ..analytics.metrics import records


class BadRequestError(ValueError):
    """Invalid user input that should become an HTTP 400/422."""


class NotFoundError(LookupError):
    """Requested entity does not exist (HTTP 404)."""


def meta(model: AnalyticsModel, f: Filters, record_count: int) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "filters": f.describe(),
        "record_count": int(record_count),
        "snapshot_date": model.snapshot_date.isoformat(),
        "period_start": model.period_start.isoformat(),
        "period_end": model.period_end.isoformat(),
        "synthetic_data": True,
    }


def months_in(lines: pd.DataFrame) -> int:
    return int(lines["month"].nunique()) if len(lines) else 0


def sort_frame(df: pd.DataFrame, sort_by: str | None, sort_dir: str, allowed: set[str], default: str) -> pd.DataFrame:
    col = sort_by or default
    if col not in allowed:
        raise BadRequestError(f"Cannot sort by '{col}'. Allowed: {', '.join(sorted(allowed))}")
    if sort_dir not in ("asc", "desc"):
        raise BadRequestError("sort_dir must be 'asc' or 'desc'")
    return df.sort_values(col, ascending=sort_dir == "asc", na_position="last", kind="mergesort")


def paginate(df: pd.DataFrame, page: int, page_size: int) -> dict:
    total = int(len(df))
    pages = max(1, math.ceil(total / page_size)) if page_size else 1
    page = max(1, page)
    start = (page - 1) * page_size
    return {
        "rows": records(df.iloc[start:start + page_size]),
        "page": page,
        "page_size": page_size,
        "total_rows": total,
        "total_pages": pages,
    }


def text_search(df: pd.DataFrame, query: str | None, columns: list[str]) -> pd.DataFrame:
    if not query:
        return df
    q = query.strip().lower()
    if not q:
        return df
    mask = pd.Series(False, index=df.index)
    for c in columns:
        mask |= df[c].astype(str).str.lower().str.contains(q, regex=False, na=False)
    return df[mask]


DISCOUNT_BANDS = ([-0.001, 0.0001, 0.10, 0.20, 0.30, 0.45, 1.01],
                  ["No discount", "0-10%", "10-20%", "20-30%", "30-45%", "45%+"])
DELAY_BANDS = ([-100, 0.5, 2.5, 5.5, 1000], ["On time / early", "1-2 days late", "3-5 days late", "6+ days late"])
VALUE_BANDS = ([-1, 500, 1000, 2500, 10000, 1e12],
               ["< INR 500", "INR 500-1k", "INR 1k-2.5k", "INR 2.5k-10k", "INR 10k+"])


def band(series: pd.Series, spec) -> pd.Categorical:
    edges, labels = spec
    return pd.cut(series, bins=edges, labels=labels, right=False if spec is DELAY_BANDS else True)


def rate_table(lines: pd.DataFrame, key: pd.Series | str, order: list[str] | None = None) -> list[dict]:
    """Unit/ order return rate by an arbitrary grouping (used for band charts)."""
    df = lines.assign(_k=key if not isinstance(key, str) else lines[key])
    df = df[df["is_eligible"]]
    if df.empty:
        return []
    g = df.groupby("_k", observed=True).agg(
        lines=("order_line_id", "count"), units=("units", "sum"), returned_units=("returned_units", "sum"),
        exposure=("risk_exposure", "sum"))
    g["unit_return_rate"] = np.where(g["units"] > 0, g["returned_units"] / g["units"].replace(0, 1), np.nan)
    if order:
        g = g.reindex([o for o in order if o in g.index])
    g = g.reset_index().rename(columns={"_k": "label"})
    g["label"] = g["label"].astype(str)
    return records(g)
