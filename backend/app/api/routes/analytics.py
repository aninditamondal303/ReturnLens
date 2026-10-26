"""Analytical page endpoints. Routes are thin: validation here, calculations in services/analytics."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query

from ...analytics import config
from ...analytics.data_model import AnalyticsModel
from ...analytics.filters import Filters
from ...analytics.scenario import ScenarioParams, parse_overrides
from ...schemas import responses as R
from ...services import (geography_service, leakage_service, overview, product_service, risk_service,
                         simulator_service)
from ...services.common import BadRequestError
from ..deps import csv_response, get_filters, get_model

router = APIRouter(tags=["analytics"])

SortDir = Literal["asc", "desc"]
Format = Literal["json", "csv"]


@router.get("/overview", response_model=R.OverviewResponse, summary="Executive Overview")
def get_overview(f: Filters = Depends(get_filters), model: AnalyticsModel = Depends(get_model)) -> dict:
    return overview.build(model, f)


@router.get("/returns", response_model=R.RiskResponse, summary="Return Risk Analysis (historical assessment)")
def get_returns(f: Filters = Depends(get_filters), model: AnalyticsModel = Depends(get_model)) -> dict:
    return risk_service.build(model, f)


@router.get("/risk-orders", response_model=R.RiskOrdersResponse, summary="Scored order lines (paginated or CSV)")
def get_risk_orders(
    f: Filters = Depends(get_filters),
    model: AnalyticsModel = Depends(get_model),
    risk_band: Optional[str] = Query("High", description="Low, Medium, High (comma-separated) or 'all'"),
    return_status: Optional[str] = Query(None, description="Actual return status filter (comma-separated)"),
    search: Optional[str] = Query(None, max_length=100),
    sort_by: Optional[str] = Query("risk_score"),
    sort_dir: SortDir = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    format: Format = Query("json"),
):
    bands = Filters.parse_list(risk_band)
    statuses = Filters.parse_list(return_status)
    if format == "csv":
        df = risk_service.order_table(model, f, bands, statuses, search, sort_by, sort_dir)
        return csv_response(df, "shopsphere_risk_orders" + (f"_{'-'.join(bands)}" if bands else ""), f)
    return risk_service.order_page(model, f, bands, statuses, search, sort_by, sort_dir, page, page_size)


@router.get("/profit-leakage", response_model=R.LeakageResponse, summary="Profit Leakage bridge and category table")
def get_profit_leakage(f: Filters = Depends(get_filters), model: AnalyticsModel = Depends(get_model)) -> dict:
    return leakage_service.build(model, f)


@router.get("/profit-leakage/products", response_model=R.CategoryProductsResponse,
            summary="Drill-down: products within one category")
def get_leakage_products(category: str = Query(..., min_length=1), f: Filters = Depends(get_filters),
                         model: AnalyticsModel = Depends(get_model)) -> dict:
    return leakage_service.category_products(model, f, category)


@router.get("/order-lines", response_model=R.OrderLinesResponse, summary="Drill-down: order lines (paginated or CSV)")
def get_order_lines(
    f: Filters = Depends(get_filters),
    model: AnalyticsModel = Depends(get_model),
    product_id: Optional[str] = Query(None),
    returned_only: bool = Query(False),
    search: Optional[str] = Query(None, max_length=100),
    sort_by: Optional[str] = Query("order_date"),
    sort_dir: SortDir = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    format: Format = Query("json"),
):
    if format == "csv":
        df = leakage_service.order_lines_frame(model, f, product_id, search, sort_by, sort_dir, returned_only)
        return csv_response(df, f"shopsphere_order_lines{'_' + product_id if product_id else ''}", f)
    return leakage_service.order_lines_page(model, f, product_id, search, sort_by, sort_dir, page, page_size,
                                            returned_only)


@router.get("/products", response_model=R.ProductsResponse, summary="Product Intelligence spotlights and scatter")
def get_products(f: Filters = Depends(get_filters), model: AnalyticsModel = Depends(get_model)) -> dict:
    return product_service.build(model, f)


@router.get("/products/table", response_model=R.ProductTableResponse, summary="Product table (paginated or CSV)")
def get_product_table(
    f: Filters = Depends(get_filters),
    model: AnalyticsModel = Depends(get_model),
    product_category: Optional[str] = Query(None, description="Page-level category filter"),
    risk: Optional[Literal["High", "Elevated", "Normal"]] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    sort_by: Optional[str] = Query("gmv"),
    sort_dir: SortDir = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    format: Format = Query("json"),
):
    if format == "csv":
        df = product_service.table(model, f, product_category, search, sort_by, sort_dir, risk)
        return csv_response(df, "shopsphere_products", f)
    return product_service.table_page(model, f, product_category, search, sort_by, sort_dir, page, page_size, risk)


@router.get("/products/{product_id}", response_model=R.ProductDetailResponse, summary="Product detail panel")
def get_product_detail(product_id: str, f: Filters = Depends(get_filters),
                       model: AnalyticsModel = Depends(get_model)) -> dict:
    return product_service.detail(model, f, product_id)


@router.get("/geography", response_model=R.GeographyResponse, summary="Customer & Geography")
def get_geography(f: Filters = Depends(get_filters), model: AnalyticsModel = Depends(get_model)) -> dict:
    return geography_service.build(model, f)


@router.get("/what-if", response_model=R.WhatIfResponse, summary="What-If Simulator (hypothetical estimates)")
def get_what_if(
    f: Filters = Depends(get_filters),
    model: AnalyticsModel = Depends(get_model),
    return_reduction: float = Query(0.10, ge=0.0, le=0.30, description="Share of refunded returns avoided"),
    logistics_reduction: float = Query(0.10, ge=0.0, le=0.30, description="Reverse-logistics cost efficiency"),
    write_off_reduction: float = Query(0.20, ge=0.0, le=0.50, description="Write-off reduction on remaining returns"),
    retained_sale_share: float = Query(0.65, ge=0.0, le=1.0, description="Avoided returns that become kept sales"),
    prevention_spend: float = Query(0.0, ge=0.0, le=1e9, description="Intervention spend in INR for the period"),
    category_overrides: Optional[str] = Query(None, description="e.g. 'Footwear:20,Women\\'s Fashion:15' (percent)"),
) -> dict:
    try:
        overrides = parse_overrides(category_overrides)
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
    params = ScenarioParams(return_reduction, logistics_reduction, write_off_reduction, retained_sale_share,
                            prevention_spend, overrides)
    return simulator_service.build(model, f, params)


@router.get("/anomalies", response_model=R.AnomalyResponse, summary="Explainable monthly anomaly flags")
def get_anomalies(
    f: Filters = Depends(get_filters),
    model: AnalyticsModel = Depends(get_model),
    min_units: int = Query(config.ANOMALY_MIN_UNITS, ge=10, le=5000),
    min_returns: int = Query(config.ANOMALY_MIN_RETURNS, ge=3, le=1000),
    rate_lift: float = Query(config.ANOMALY_RATE_LIFT, ge=1.05, le=5.0),
    z_threshold: float = Query(config.ANOMALY_Z, ge=1.0, le=6.0),
) -> dict:
    return simulator_service.detect_anomalies(model, f, min_units, min_returns, rate_lift, z_threshold)
