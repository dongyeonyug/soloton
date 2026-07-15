"""신규 KHOA/KMA 공공데이터 계약과 방어 파싱 검증.

픽스처는 2026-07-11 실제 응답 구조(키·원문 비커밋)를 반영한다.
KHOA: {header, body:{items:{item:[...]}}}, 필드 wvhgt/wspd/crsp(cm/s)/wtem.
KMA getPwnStatus: response.body.items.item[].t6 = 'o <특보명> : <지역>' 세그먼트.
"""

import asyncio
from datetime import date

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
    captured = []

    async def fake_fetch(url, params=None, **kwargs):
        captured.append({"url": url, "params": params})
        if url == khoa.KHOA_TIDE_URL:
            return {"header": {"resultCode": "00"}, "body": {"items": {"item": []}}}
        return {"header": {"resultCode": "00"}, "body": {"items": {"item": [_KHOA_ITEM]}}}

    monkeypatch.setattr(khoa, "fetch_json", fake_fetch)
    result = asyncio.run(khoa.fetch_spot(_live_spot(), "key"))

    buoy_call = next(call for call in captured if call["url"] == khoa.KHOA_URL)
    assert buoy_call["url"] == khoa.KHOA_URL
    assert buoy_call["params"]["serviceKey"] == "key"
    assert buoy_call["params"]["obsCode"] == "TW_0062"
    assert buoy_call["params"]["type"] == "json"
    assert buoy_call["params"]["reqDate"]
    assert buoy_call["params"]["min"] == 60
    assert {"pageNo", "numOfRows"} <= buoy_call["params"].keys()
    # wvhgt=파고(m), wspd=풍속(m/s), wtem=수온(°C) 그대로; crsp 38.1cm/s → 0.381 m/s
    assert result == {
        Metric.WAVE_HEIGHT: 0.4,
        Metric.WIND_SPEED: 0.9,
        Metric.WATER_TEMP: 22.1,
        Metric.CURRENT_SPEED: 0.381,
    }


def test_khoa_uses_tide_endpoint_and_merges_tide_level(monkeypatch):
    spot = _live_spot().model_copy(update={"khoa_tide_obs_code": "DT_0005"})
    captured = []

    async def fake_fetch(url, params=None, **kwargs):
        captured.append({"url": url, "params": params})
        if url == khoa.KHOA_URL:
            return {"body": {"items": {"item": [{"wvhgt": "0.4"}]}}}
        return {"body": {"items": {"item": [{"obsrvnDt": "2026-07-11 00:00", "tideLevel": "123"}]}}}

    monkeypatch.setattr(khoa, "fetch_json", fake_fetch)
    result = asyncio.run(khoa.fetch_spot(spot, "buoy-key", "tide-key"))

    tide_call = next(call for call in captured if call["url"] == khoa.KHOA_TIDE_URL)
    assert tide_call["params"]["serviceKey"] == "tide-key"
    assert tide_call["params"]["obsCode"] == "DT_0005"
    assert result[Metric.WAVE_HEIGHT] == 0.4
    assert result[Metric.TIDE_LEVEL] == 123.0


def test_khoa_tide_parser_accepts_aliases_and_bad_values():
    raw = {"body": {"items": {"item": [
        {"tideLevel": "-"},
        {"tideLevel": "bad"},
        {"tdLvl": "88.5"},
    ]}}}
    assert khoa._parse_tide(raw) == {Metric.TIDE_LEVEL: 88.5}
    assert khoa._parse_tide({"body": {"items": {"item": [{"tideLevel": "-"}]}}}) is None


def test_khoa_tide_parser_reads_live_bsc_tide_height_field():
    raw = {"body": {"items": {"item": [
        {"obsrvnDt": "2026-07-16 00:00", "bscTdlvHgt": 112.0}
    ]}}}
    parsed = khoa._with_observed_at(khoa._parse_tide(raw), raw)
    assert parsed == {Metric.TIDE_LEVEL: 112.0}
    assert parsed.metric_observed_at[Metric.TIDE_LEVEL].isoformat() == "2026-07-15T15:00:00"


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


def test_kma_warning_list_uses_period_and_station_filters(monkeypatch):
    captured = {}

    async def fake_fetch(url, params=None, **kwargs):
        captured.update(url=url, params=params)
        return {"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": [{
            "stnId": "159", "tmFc": 202607150030, "tmSeq": 26,
            "title": "[특보] 제07-26호 : 2026.07.15.00:30 / 풍랑주의보 발표 (*)",
        }]}}}}

    monkeypatch.setattr(kma, "fetch_json", fake_fetch)
    records = asyncio.run(
        kma.fetch_warning_list(
            "key",
            from_date=date(2026, 7, 10),
            to_date=date(2026, 7, 16),
            station_id="159",
        )
    )

    assert captured["url"] == kma.KMA_WARNING_LIST_URL
    assert captured["params"]["stnId"] == "159"
    assert captured["params"]["fromTmFc"] == "20260710"
    assert captured["params"]["toTmFc"] == "20260716"
    assert records == [
        kma.WarningListRecord(
            stn_id="159",
            tm_fc="202607150030",
            tm_seq=26,
            title="[특보] 제07-26호 : 2026.07.15.00:30 / 풍랑주의보 발표 (*)",
        )
    ]


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


def test_kma_scope_preserves_source_text_and_exact_busan_zone(monkeypatch):
    captured = {}

    async def fake_fetch(url, params=None, **kwargs):
        captured.update(url=url, params=params)
        return {"response": {"body": {"items": {"item": [{
            "t6": (
                "o 풍랑주의보 : 남해동부앞바다, 제주도앞바다\n"
                "o 폭염경보 : 부산(부산서부), 대구"
            )
        }]}}}}

    monkeypatch.setattr(kma, "fetch_json", fake_fetch)
    scope = asyncio.run(kma.fetch_busan_coastal_scope("key"))

    assert captured["url"] == kma.KMA_URL
    assert scope is not None
    assert scope.advisory is AdvisoryKind.WIND_WAVE_WARNING
    assert scope.matched_segments[0].matched_zones == ("남해동부앞바다",)
    assert "폭염경보" in scope.source_t6


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


def test_every_spot_uses_a_verified_nearest_tide_station():
    from app.spots import TIDE_STATIONS, nearest_tide_reference_for, tide_reference_for

    assert {spot.khoa_tide_obs_code for spot in all_spots()} <= set(TIDE_STATIONS)
    for spot in all_spots():
        configured, configured_distance = tide_reference_for(spot)
        nearest, nearest_distance = nearest_tide_reference_for(spot)
        assert configured.code == nearest.code
        assert configured_distance == nearest_distance

    assert get_spot("imnang").khoa_tide_obs_code == "DT_0020"


def test_tide_reference_reports_station_and_distance():
    from app.spots import tide_reference_for

    station, distance = tide_reference_for(get_spot("haeundae"))
    assert station.name == "부산 조위관측소"
    assert station.code == "DT_0005"
    assert distance > 0
