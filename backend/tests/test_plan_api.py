"""Phase 1 계획 API 계약과 브라우저 CORS 경계."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
import pytest

import app.service as service
from app.ingest.cache import SnapshotDoc, SpotSnapshot
from app.main import app
from app.models import Advisory, AdvisoryKind, ForecastPoint

client = TestClient(app)
KST = ZoneInfo("Asia/Seoul")


def _fresh_doc() -> tuple[SnapshotDoc, datetime]:
    now = datetime.now(KST)
    forecast_at = (now + timedelta(hours=2)).replace(
        minute=0, second=0, microsecond=0, tzinfo=None
    )
    snapshot_at = now.astimezone(UTC).replace(tzinfo=None)
    return (
        SnapshotDoc(
            snapshot_as_of=snapshot_at,
            source="test",
            spots={
                "haeundae": SpotSnapshot(
                    observations=[],
                    advisory=Advisory(kind=AdvisoryKind.NONE, source="기상청 특보"),
                    forecast=[ForecastPoint(time=forecast_at, wave_height=0.5, wind_speed=5.0)],
                    forecast_collected_at=snapshot_at,
                )
            },
        ),
        forecast_at,
    )


def _body(forecast_at: datetime) -> dict[str, str]:
    return {
        "spot_id": "haeundae",
        "activity": "water_play",
        "requested_at": forecast_at.replace(tzinfo=KST).isoformat(),
    }


def test_plan_options_and_briefing_use_the_same_real_forecast_time(monkeypatch):
    doc, forecast_at = _fresh_doc()
    monkeypatch.setattr(service, "get_snapshot", lambda: doc)

    options = client.get("/api/plans/options/haeundae")
    assert options.status_code == 200
    options_body = options.json()
    assert options_body["activity"] == "water_play"
    assert options_body["forecast_times"] == [forecast_at.isoformat()]

    response = client.post("/api/plans/briefing", json=_body(forecast_at))
    assert response.status_code == 200
    body = response.json()
    assert body["data_state"] == "ready"
    assert body["coverage_state"] == "detailed"
    assert body["forecast_conditions"]["forecast_at"] == forecast_at.isoformat()
    assert body["forecast_conditions"]["grade"] == "SAFE"
    assert body["current_advisory"]["scope_label"] == "현재 기준 · 미래 보장 아님"
    assert "llm_prose" not in body
    assert "prose_status" not in body


def test_plan_api_returns_invalid_time_without_nearest_time_substitution(monkeypatch):
    doc, forecast_at = _fresh_doc()
    monkeypatch.setattr(service, "get_snapshot", lambda: doc)
    missing_time = forecast_at + timedelta(hours=1)

    response = client.post("/api/plans/briefing", json=_body(missing_time))

    assert response.status_code == 200
    body = response.json()
    assert body["data_state"] == "invalid_time"
    assert body["forecast_conditions"] is None
    assert "다시 선택" in body["action"]


def test_plan_api_rejects_a_time_without_kst_offset():
    response = client.post(
        "/api/plans/briefing",
        json={
            "spot_id": "haeundae",
            "activity": "water_play",
            "requested_at": "2026-07-18T10:00:00",
        },
    )

    assert response.status_code == 422
    assert "Asia/Seoul" in response.text


def test_plan_options_unknown_spot_is_404():
    response = client.get("/api/plans/options/nonexistent")
    assert response.status_code == 404


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_plan_post_is_allowed_by_cors_preflight(origin):
    response = client.options(
        "/api/plans/briefing",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]
