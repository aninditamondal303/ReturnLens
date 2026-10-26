"""Global filter state applied identically to order lines and returns."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta

import pandas as pd


@dataclass(frozen=True)
class Filters:
    start_date: date | None = None
    end_date: date | None = None
    categories: tuple[str, ...] = field(default_factory=tuple)
    regions: tuple[str, ...] = field(default_factory=tuple)
    channels: tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def parse_list(value: str | None) -> tuple[str, ...]:
        """Comma-separated list -> tuple; empty / 'all' -> no filter."""
        if not value:
            return ()
        items = tuple(v.strip() for v in value.split(",") if v.strip())
        return () if any(i.lower() == "all" for i in items) else items

    def describe(self) -> dict:
        return {
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "categories": list(self.categories),
            "regions": list(self.regions),
            "channels": list(self.channels),
        }

    def without_dates(self) -> "Filters":
        return replace(self, start_date=None, end_date=None)

    def previous_period(self, data_start: date) -> "Filters | None":
        """Equivalent immediately-preceding period, or None when data does not fully cover it."""
        if not self.start_date or not self.end_date:
            return None
        length = (self.end_date - self.start_date).days
        prev_end = self.start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=length)
        if prev_start < data_start:
            return None
        return replace(self, start_date=prev_start, end_date=prev_end)


def apply(df: pd.DataFrame, f: Filters, date_col: str = "order_date") -> pd.DataFrame:
    """Filter a line- or return-level frame. Returns are filtered by their ORIGINAL order date."""
    mask = pd.Series(True, index=df.index)
    if f.start_date:
        mask &= df[date_col] >= pd.Timestamp(f.start_date)
    if f.end_date:
        mask &= df[date_col] <= pd.Timestamp(f.end_date)
    if f.categories:
        mask &= df["category"].isin(f.categories)
    if f.regions:
        mask &= df["shipping_region"].isin(f.regions)
    if f.channels:
        mask &= df["sales_channel"].isin(f.channels)
    return df[mask]
