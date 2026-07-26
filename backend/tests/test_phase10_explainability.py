"""
NEXUS AI — Phase 10 Test Suite
Tests for Explainability Engine:
  - Factor waterfall weight generation (PCR 18%, OI 21%, News 12%, FII 15%, Indicators 20%, Greeks 14%)
  - SHAP proxy values and reason output
  - Explainability REST API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from modules.explainability.explainability_engine import (
    ExplainabilityEngine, ExplainabilityReport, FactorWeight, explainability_engine
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def engine():
    return ExplainabilityEngine()


# ─── Explainability Engine Tests ──────────────────────────────────────────────

class TestExplainabilityEngine:

    def test_generate_report_structure(self, engine):
        report = engine.generate_report("BUY_CALL", 91.0)
        assert isinstance(report, ExplainabilityReport)
        assert report.recommendation == "BUY_CALL"
        assert report.confidence == 91.0
        assert len(report.factor_breakdown) == 6

    def test_factor_weights_match_user_specification(self, engine):
        report = engine.generate_report()
        weights = {f.factor_name: f.weight_pct for f in report.factor_breakdown}
        assert weights["PCR"] == 18.0
        assert weights["OI"] == 21.0
        assert weights["News"] == 12.0
        assert weights["FII"] == 15.0
        assert weights["Indicators"] == 20.0
        assert weights["Greeks"] == 14.0
        assert sum(weights.values()) == 100.0

    def test_shap_values_in_range(self, engine):
        report = engine.generate_report()
        for f in report.factor_breakdown:
            assert -1.0 <= f.shap_value <= 1.0


# ─── Explainability API Tests ─────────────────────────────────────────────────

class TestExplainabilityAPI:

    def test_report_endpoint_200(self, client):
        resp = client.get("/api/v1/explainability/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendation" in data
        assert "confidence" in data
        assert "factor_weights" in data
        assert len(data["factor_weights"]) == 6

    def test_report_weights_sum(self, client):
        data = client.get("/api/v1/explainability/report").json()
        total = sum(f["weight_pct"] for f in data["factor_weights"])
        assert total == 100.0
