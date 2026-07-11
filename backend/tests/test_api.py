"""API 라우터 스모크 — 엔드포인트 계약 검증."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["spot_count"] >= 10


def test_list_spots():
    r = client.get("/api/spots")
    assert r.status_code == 200
    assert len(r.json()) >= 10


def test_overview_has_grades():
    r = client.get("/api/overview", params={"activity": "레저"})
    assert r.status_code == 200
    body = r.json()
    assert "snapshot_as_of" in body
    grades = {s["grade"] for s in body["spots"]}
    assert grades <= {"SAFE", "CAUTION", "DANGER"}


def test_risk_and_briefing():
    r = client.get("/api/risk/haeundae", params={"activity": "물놀이"})
    assert r.status_code == 200
    assert r.json()["grade"] in {"SAFE", "CAUTION", "DANGER"}

    b = client.get("/api/briefing/haeundae", params={"activity": "물놀이"})
    assert b.status_code == 200
    body = b.json()
    assert "template_text" in body
    assert "llm_prose" in body


def test_unknown_spot_404():
    assert client.get("/api/risk/nonexistent").status_code == 404


def test_observations():
    r = client.get("/api/observations/cheongsapo")
    assert r.status_code == 200
    metrics = {o["metric"] for o in r.json()["observations"]}
    assert "wind_speed" in metrics
