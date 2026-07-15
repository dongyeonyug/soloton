"""API 라우터 스모크 — 엔드포인트 계약 검증."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["spot_count"] >= 10


def test_root_uses_the_generic_coastal_activity_disclaimer():
    r = client.get("/")
    assert r.status_code == 200
    disclaimer = r.json()["disclaimer"]
    assert "해안 활동" in disclaimer
    assert "항해" not in disclaimer
    assert "입수" not in disclaimer


def test_list_spots():
    r = client.get("/api/spots")
    assert r.status_code == 200
    assert len(r.json()) >= 10


def test_overview_has_grades():
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()
    assert "snapshot_as_of" in body
    assert "activity" not in body
    grades = {s["grade"] for s in body["spots"]}
    assert grades <= {"SAFE", "CAUTION", "DANGER"}


def test_risk_and_briefing():
    r = client.get("/api/risk/haeundae")
    assert r.status_code == 200
    assert r.json()["grade"] in {"SAFE", "CAUTION", "DANGER"}

    b = client.get("/api/briefing/haeundae")
    assert b.status_code == 200
    body = b.json()
    assert "template_text" in body
    assert "llm_prose" in body
    assert body["prose_status"] in {
        "verified",
        "blocked_by_guard",
        "generation_unavailable",
        "deterministic_fallback",
    }
    assert body["has_missing_critical"] is False
    assert body["advisory"]["is_missing"] is False
    citation = body["citations"][0]
    assert citation["data_status"] in {
        "observed", "forecast", "available", "missing", "stale"
    }
    assert "checked_source" in citation
    assert "is_critical" in citation
    assert "missing_reason" in citation
    assert "reference_note" in citation
    assert citation["rule_evidence"] in {
        "official_baseline", "conservative_mapping", None
    }
    assert body["decision_steps"]
    assert body["decision_steps"][-1] == {
        "label": "최종 위험도",
        "detail": "지표 중 가장 높은 등급, 특보 상향, 결측 보수 규칙을 모두 반영",
        "result_grade": body["grade"],
        "rule_evidence": None,
    }
    assessment = body["safe_window_assessment"]
    assert assessment["status"] in {
        "available",
        "forecast_unavailable",
        "no_future_forecast",
        "incomplete_forecast",
        "no_safe_window",
    }
    assert assessment["safe_window"] == body["safe_window"]
    assert "llm_used" not in body
    assert "activity" not in body


def test_public_contract_has_no_activity_parameter():
    paths = app.openapi()["paths"]
    for path in ("/api/overview", "/api/risk/{spot_id}", "/api/briefing/{spot_id}"):
        parameters = paths[path]["get"].get("parameters", [])
        assert all(parameter["name"] != "activity" for parameter in parameters)


def test_unknown_spot_404():
    assert client.get("/api/risk/nonexistent").status_code == 404


def test_observations():
    r = client.get("/api/observations/cheongsapo")
    assert r.status_code == 200
    metrics = {o["metric"] for o in r.json()["observations"]}
    assert "wind_speed" in metrics
    body = r.json()
    assert body["forecast_status"] in {
        "available", "empty_response", "source_timeout", "source_unavailable", "legacy_unknown"
    }
    assert "forecast_missing_reason" in body
    assert "forecast_collected_at" in body


def test_briefing_explains_missing_critical_input(monkeypatch):
    """T3: 라이브 스냅샷과 무관하게 핵심 결측 API 계약을 검증한다."""
    import app.service as service
    from app.ingest.cache import get_snapshot
    from app.models import Metric

    doc = get_snapshot().model_copy(deep=True)
    snap = doc.spot("dadaepo")
    assert snap is not None
    snap.observations = [
        observation.model_copy(
            update={"value": None, "observed_at": None, "is_missing": True}
        )
        if observation.metric is Metric.WAVE_HEIGHT
        else observation
        for observation in snap.observations
    ]
    monkeypatch.setattr(service, "get_snapshot", lambda: doc)

    r = client.get("/api/briefing/dadaepo")
    assert r.status_code == 200
    body = r.json()
    assert body["has_missing_critical"] is True

    wave = next(c for c in body["citations"] if c["label"] == "유의파고")
    assert wave["data_status"] == "missing"
    assert wave["is_critical"] is True
    assert wave["checked_source"]
    assert wave["missing_reason"] is None
