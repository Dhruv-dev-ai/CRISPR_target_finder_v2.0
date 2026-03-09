"""
Unit tests for CRISPR Target Finder — REST API (api.py)
========================================================
Tests all API endpoints: /api/grna, /api/score, /api/ot, /api/health.
"""

import json
import pytest
from api import app


@pytest.fixture
def client():
    """Create a Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ─────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_json(self, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert "version" in data


# ─────────────────────────────────────────────────────────────
# gRNA Endpoint
# ─────────────────────────────────────────────────────────────

class TestGRNAEndpoint:
    """Tests for the /api/grna endpoint."""

    def test_find_targets(self, client):
        resp = client.post("/api/grna",
            json={"sequence": "ATCGATCGATCGATCGATCGTGG" * 5},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "total_targets" in data

    def test_missing_sequence(self, client):
        resp = client.post("/api/grna",
            json={},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_json_request(self, client):
        resp = client.post("/api/grna",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400

    def test_empty_sequence(self, client):
        resp = client.post("/api/grna",
            json={"sequence": ""},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_with_input_type(self, client):
        resp = client.post("/api/grna",
            json={
                "sequence": "ATCGATCGATCGATCGATCGTGG" * 3,
                "input_type": "dna",
            },
            content_type="application/json",
        )
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────
# Score Endpoint
# ─────────────────────────────────────────────────────────────

class TestScoreEndpoint:
    """Tests for the /api/score endpoint."""

    def test_score_grnas(self, client):
        resp = client.post("/api/score",
            json={"grnas": ["ATCGATCGATCGATCGATCG", "GCTAGCTAGCTAGCTAGCTA"]},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert len(data["scores"]) == 2

    def test_score_has_fields(self, client):
        resp = client.post("/api/score",
            json={"grnas": ["ATCGATCGATCGATCGATCG"]},
            content_type="application/json",
        )
        data = resp.get_json()
        score = data["scores"][0]
        assert "Doench_Score" in score
        assert "ML_Score" in score
        assert "GC_Content" in score

    def test_missing_grnas_field(self, client):
        resp = client.post("/api/score",
            json={},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_empty_grna_list(self, client):
        resp = client.post("/api/score",
            json={"grnas": []},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_short_grna_error(self, client):
        resp = client.post("/api/score",
            json={"grnas": ["AT"]},
            content_type="application/json",
        )
        data = resp.get_json()
        assert "error" in data["scores"][0]


# ─────────────────────────────────────────────────────────────
# Off-Target Endpoint
# ─────────────────────────────────────────────────────────────

class TestOffTargetEndpoint:
    """Tests for the /api/ot endpoint."""

    def test_off_target_analysis(self, client):
        resp = client.post("/api/ot",
            json={
                "grna": "ATCGATCGATCGATCGATCG",
                "sequence": "ATCGATCGATCGATCGATCGTGG" * 5,
            },
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "specificity_score" in data
        assert "risk_level" in data

    def test_missing_grna(self, client):
        resp = client.post("/api/ot",
            json={"sequence": "ATCGATCG" * 10},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_missing_sequence(self, client):
        resp = client.post("/api/ot",
            json={"grna": "ATCGATCGATCGATCGATCG"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_short_grna_rejected(self, client):
        resp = client.post("/api/ot",
            json={"grna": "ATCG", "sequence": "ATCGATCG" * 10},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_custom_max_mismatches(self, client):
        resp = client.post("/api/ot",
            json={
                "grna": "ATCGATCGATCGATCGATCG",
                "sequence": "ATCGATCGATCGATCGATCGTGG" * 3,
                "max_mismatches": 2,
            },
            content_type="application/json",
        )
        data = resp.get_json()
        if data.get("off_targets"):
            for ot in data["off_targets"]:
                assert ot["mismatches"] <= 2
