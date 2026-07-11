"""신규 KHOA/KMA 공공데이터 계약과 방어 파싱 검증.

픽스처는 2026-07-11 실제 응답 구조(키·원문 비커밋)를 반영한다.
KHOA: {header, body:{items:{item:[...]}}}, 필드 wvhgt/wspd/crsp(cm/s)/wtem.
KMA getPwnStatus: response.body.items.item[].t6 = 'o <특보명> : <지역>' 세그먼트.
"""

import asyncio

from app.clients import khoa, kma
from app.models import AdvisoryKind, Metric
from app.spots import all_spots, get_spot


def _live_spot():
    return get_spot("haeundae").model_copy(update={"khoa_obs_code": "TW_0062"})


# 실제 twRecent 응답 형태(값은 대표치, 키·원문 비커밋)
_KHOA_ITEM = {
    "obsvtrNm": "부이", "lat": 35.0, "lot": 129.0, "obsrvnDt": "2026-07-11 00:00",
    "wndrct": 303.5, "wspd": "0.9", "maxMmntWspd": 1.8, "artmp": 24.0, "atmpr": 1013.0,
    "wvhgt": "0.4", "wvpd": 5.7, "crdir": 271.9, "crsp": "38.1", "wtem": "22.1", "slnty": 33.0,
}


def test_khoa_uses_new_endpoint_and_official_params(monkeypatch):
    captured = {}

    async def fake_fetch(url, params=None, **kwargs):
        captured.update(url=url, params=params)
        return {"header": {"resultCode": "00"}, "body": {"items": {"item": [_KHOA_ITEM]}}}

    monkeypatch.setattr(khoa, "fetch_json", fake_fetch)
    result = asyncio.run(khoa.fetch_spot(_live_spot(), "key"))

    assert captured["url"] == khoa.KHOA_URL
    assert captured["params"]["serviceKey"] == "key"
    assert captured["params"]["obsCode"] == "TW_0062"
    assert captured["params"]["type"] == "json"
    assert captured["params"]["reqDate"]
    assert captured["params"]["min"] == 60
    assert {"pageNo", "numOfRows"} <= captured["params"].keys()
    # wvhgt=파고(m), wspd=풍속(m/s), wtem=수온(°C) 그대로; crsp 38.1cm/s → 0.381 m/s
    assert result == {
        Metric.WAVE_HEIGHT: 0.4,
        Metric.WIND_SPEED: 0.9,
        Metric.WATER_TEMP: 22.1,
        Metric.CURRENT_SPEED: 0.381,
    }


def test_khoa_current_speed_converts_cm_per_s_to_m_per_s():
    raw = {"body": {"items": {"item": [{"wvhgt": "1.0", "crsp": "150"}]}}}
    parsed = khoa._parse(raw)
    assert parsed[Metric.CURRENT_SPEED] == 1.5  # 150 cm/s → 1.5 m/s
    assert parsed[Metric.WAVE_HEIGHT] == 1.0


def test_khoa_parses_latest_and_ignores_bad_values():
    raw = {"body": {"items": {"item": [
        {"wvhgt": "-", "crsp": None},
        {"wvhgt": "1.2", "crsp": "bad", "wtem": 19.5},
    ]}}}
    assert khoa._parse(raw) == {Metric.WAVE_HEIGHT: 1.2, Metric.WATER_TEMP: 19.5}
    assert khoa._parse({"body": {"items": {"item": []}}}) is None


def test_kma_uses_current_status_and_never_returns_wind(monkeypatch):
    captured = {}

    async def fake_fetch(url, params=None, **kwargs):
        captured.update(url=url, params=params)
        return {"response": {"body": {"items": {"item": [
            {"t6": "o 풍랑주의보 : 남해동부앞바다, 제주도앞바다", "t7": "", "other": "o 없음"}
        ]}}}}

    monkeypatch.setattr(kma, "fetch_json", fake_fetch)
    result = asyncio.run(kma.fetch_spot(get_spot("haeundae"), "key"))

    assert captured["url"] == kma.KMA_URL
    assert captured["params"]["ServiceKey"] == "key"
    assert {"pageNo", "numOfRows", "dataType"} <= captured["params"].keys()
    assert result == {"advisory": AdvisoryKind.WIND_WAVE_WARNING}
    assert "wind_speed" not in result


def test_kma_ignores_farsea_warning_and_busan_land_false_positive():
    """실제 버그 회귀: 풍랑경보가 제주/먼바다이고 '부산'은 폭염(육상)일 때 → 특보 없음."""
    raw = {"response": {"body": {"items": {"item": [{
        "t6": (
            "o 강풍주의보 : 전라남도(흑산도.홍도)\n"
            "o 풍랑경보 : 남해동부바깥먼바다, 제주도앞바다\n"
            "o 풍랑주의보 : 서해남부북쪽안쪽먼바다, 남해동부안쪽먼바다\n"
            "o 폭염경보 : 부산(부산서부), 대구, 울산"
        ),
        "t7": "(1) 풍랑 예비특보\no 07월 11일 밤 : 남해동부앞바다",
    }]}}}}
    # 풍랑경보/주의보 세그먼트에 부산 연안(남해동부앞바다) 없음, 예비특보(t7) 미반영 → NONE
    assert kma._parse(raw, area="부산") == {"advisory": AdvisoryKind.NONE}


def test_kma_attributes_busan_coastal_advisory():
    raw = {"response": {"body": {"items": {"item": [{
        "t6": "o 풍랑주의보 : 남해동부앞바다, 제주도앞바다"
    }]}}}}
    assert kma._parse(raw, area="부산") == {"advisory": AdvisoryKind.WIND_WAVE_WARNING}


def test_kma_keeps_strongest_active_level():
    raw = {"response": {"body": {"items": {"item": [{
        "t6": "o 풍랑경보 : 남해동부앞바다\no 강풍주의보 : 부산(부산서부)"
    }]}}}}
    assert kma._parse(raw, area="부산") == {"advisory": AdvisoryKind.WIND_WAVE_ALERT}


def test_public_clients_remain_failure_safe(monkeypatch):
    async def fail(url, params=None, **kwargs):
        return None

    monkeypatch.setattr(khoa, "fetch_json", fail)
    monkeypatch.setattr(kma, "fetch_json", fail)
    assert asyncio.run(khoa.fetch_spot(_live_spot(), "key")) is None
    assert asyncio.run(kma.fetch_spot(get_spot("haeundae"), "key")) is None


def test_every_spot_has_a_verified_busan_area_buoy_code():
    allowed = {"TW_0062", "TW_0087", "TW_0090", "TW_0092"}
    assert {spot.khoa_obs_code for spot in all_spots()} <= allowed
