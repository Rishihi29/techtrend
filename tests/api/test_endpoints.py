"""API integration tests against the demo-built warehouse.

Requires `make demo` (CI runs the pipeline first). Verifies contracts,
pagination math, filtering, 404 semantics, and injection safety.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not Path("data/warehouse/techtrend.duckdb").exists(),
    reason="warehouse not built; run `make demo` first",
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    from api.main import app

    return TestClient(app)


class TestProducts:
    def test_pagination_math(self, client):
        page = client.get("/api/v1/products", params={"page": 1, "page_size": 7}).json()
        assert page["page_size"] == 7
        assert len(page["items"]) == 7
        assert page["total_pages"] == -(-page["total"] // 7)

    def test_category_filter_is_exhaustive(self, client):
        page = client.get(
            "/api/v1/products", params={"category": "Footwear", "page_size": 200}
        ).json()
        assert page["total"] > 0
        assert all(p["category"] == "Footwear" for p in page["items"])

    def test_search_hits_brand_tokens(self, client):
        page = client.get("/api/v1/products", params={"search": "teva"}).json()
        assert page["total"] > 0

    def test_sql_injection_attempt_is_inert(self, client):
        r = client.get("/api/v1/products", params={"search": "'; DROP TABLE dim_product;--"})
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert client.get("/api/v1/products").json()["total"] > 0  # table intact

    def test_unknown_product_is_404(self, client):
        assert client.get("/api/v1/products/999999").status_code == 404

    def test_page_size_is_capped(self, client):
        page = client.get("/api/v1/products", params={"page_size": 10_000}).json()
        assert page["page_size"] <= 200


class TestAnalytics:
    def test_kpis_reflect_warehouse(self, client):
        k = client.get("/api/v1/analytics/kpis").json()
        assert k["products"] == 500
        assert k["warehouse_rows"] == 45_000
        assert k["quality"]["composite_score"] > 0.9

    def test_forecast_has_ordered_bands(self, client):
        fc = client.get("/api/v1/products/1/forecast").json()
        assert len(fc) >= 7
        assert all(p["yhat_lower"] <= p["yhat"] <= p["yhat_upper"] for p in fc)

    def test_recommendations_never_self_refer(self, client):
        recs = client.get("/api/v1/products/1/recommendations").json()
        assert recs and all(r["product_id"] != 1 for r in recs)

    def test_metrics_exposition_format(self, client):
        body = client.get("/metrics").text
        assert "techtrend_http_requests_total" in body
