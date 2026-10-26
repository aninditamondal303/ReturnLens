"""
HTTP-level tests with FastAPI's TestClient against the generated dataset.
Skipped automatically if FastAPI/httpx are not installed.
"""
import csv
import io

import pytest


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["data_loaded"] and body["rows"]["orders"] > 15000


def test_metadata(client):
    body = client.get("/api/metadata").json()
    assert len(body["categories"]) == 10 and len(body["months"]) == 12
    assert body["return_rate_target"] == 0.08


def test_overview_and_filters(client):
    full = client.get("/api/overview").json()
    assert len(full["kpis"]) == 5 and full["anatomy"][-1]["key"] == "contribution_after"
    cat = full["leakage_map"][0]["category"]
    filtered = client.get("/api/overview", params={"category": cat}).json()
    assert filtered["summary"]["gmv"] == pytest.approx(full["leakage_map"][0]["gmv"])
    assert filtered["meta"]["filters"]["categories"] == [cat]


def test_every_page_endpoint_responds(client):
    params = {"start_date": "2026-04-01", "end_date": "2026-09-30", "region": "Maharashtra"}
    for path in ["/api/overview", "/api/returns", "/api/risk-orders", "/api/profit-leakage", "/api/products",
                 "/api/products/table", "/api/geography", "/api/what-if", "/api/anomalies", "/api/order-lines"]:
        r = client.get(path, params=params)
        assert r.status_code == 200, (path, r.text[:300])
    assert client.get("/api/data-quality").status_code == 200
    assert client.get("/api/metrics-dictionary").status_code == 200


def test_empty_filter_result(client):
    r = client.get("/api/overview", params={"region": "Atlantis"})
    assert r.status_code == 200
    assert r.json()["summary"]["gmv"] == 0 and r.json()["insights"] == []


def test_invalid_dates_return_consistent_error(client):
    r = client.get("/api/overview", params={"start_date": "2026-05-01", "end_date": "2026-01-01"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_request"
    r = client.get("/api/overview", params={"start_date": "not-a-date"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_parameters"


def test_what_if_validation_and_calculation(client):
    assert client.get("/api/what-if", params={"return_reduction": 0.5}).status_code == 422
    r = client.get("/api/what-if", params={"category_overrides": "Narnia:10"})
    assert r.status_code == 400
    base = client.get("/api/what-if", params={"return_reduction": 0, "logistics_reduction": 0,
                                              "write_off_reduction": 0}).json()["result"]
    assert base["gross_cost_savings"] == 0
    more = client.get("/api/what-if", params={"return_reduction": 0.2, "prevention_spend": 10000}).json()["result"]
    assert more["gross_cost_savings"] > 0
    assert more["net_improvement"] == pytest.approx(more["gross_cost_savings"] + more["retained_margin"] - 10000, abs=0.05)


def test_risk_orders_pagination_sort_and_csv(client):
    page = client.get("/api/risk-orders", params={"page_size": 10, "sort_by": "risk_score"}).json()
    assert len(page["rows"]) <= 10 and page["total_rows"] >= len(page["rows"])
    scores = [r["risk_score"] for r in page["rows"]]
    assert scores == sorted(scores, reverse=True)
    assert all(r["risk_band"] == "High" for r in page["rows"])
    r = client.get("/api/risk-orders", params={"format": "csv", "category": "Footwear", "risk_band": "all"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "Footwear" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert rows and {row["category"] for row in rows} == {"Footwear"}
    assert int(r.headers["x-row-count"]) == len(rows)
    assert client.get("/api/risk-orders", params={"sort_by": "password"}).status_code == 400


def test_product_detail_and_404(client):
    table = client.get("/api/products/table", params={"page_size": 1}).json()
    pid = table["rows"][0]["product_id"]
    detail = client.get(f"/api/products/{pid}").json()
    assert detail["product"]["product_id"] == pid
    assert client.get("/api/products/NOPE").status_code == 404


def test_data_explorer(client):
    prev = client.get("/api/data/returns", params={"page_size": 5, "sort_by": "refund_amount", "sort_dir": "desc"}).json()
    assert len(prev["rows"]) == 5
    refunds = [float(r["refund_amount"]) for r in prev["rows"]]
    assert refunds == sorted(refunds, reverse=True)
    assert client.get("/api/data/secrets").status_code == 404
    dl = client.get("/api/data/products/download")
    assert dl.status_code == 200 and dl.text.startswith("product_id")


def test_reload_is_real(client):
    before = client.get("/api/health").json()["loaded_at"]
    r = client.post("/api/data/reload").json()
    assert r["reloaded"] is True and r["loaded_at"] != before
