"""부산 핵심 연안 지점 (15). 좌표는 대표 지점 근사값.

``khoa_obs_code``는 국립해양조사원 해양관측부이 운영 현황의 부산권 부이 중
가장 가까운 관측소를 연결한다. 지점과 부이는 같은 위치가 아니며 거리 표는
``docs/DATA_SOURCES.md``에 기록한다. ``khoa_tide_obs_code``는 조위관측소 최신
관측데이터(`15155508`)용 코드다. 부산권 및 경계 인접 관측소 가운데 서비스 지점에
가장 가까운 관측소를 연결하며, 이 값은 직접 관측 위치가 아니라 참고 관측소다.
``kma_area``는 특보 제목의 지역 필터다.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from .models import Spot, SpotType

BUSAN_TIDE_OBS_CODE = "DT_0005"
BUSAN_NEW_PORT_TIDE_OBS_CODE = "DT_0056"
GADEOKDO_TIDE_OBS_CODE = "DT_0063"
ULSAN_TIDE_OBS_CODE = "DT_0020"


@dataclass(frozen=True)
class TideStation:
    code: str
    name: str
    lat: float
    lng: float


# 2026-07-16 dtRecent 실응답과 조위관측소 운영 현황(15146602)으로 확인한
# 부산권 및 경계 인접 조위관측소. 모든 관측소는 최신 조위 API 응답도 확인했다.
TIDE_STATIONS: dict[str, TideStation] = {
    BUSAN_TIDE_OBS_CODE: TideStation(
        code=BUSAN_TIDE_OBS_CODE,
        name="부산 조위관측소",
        lat=35.09638,
        lng=129.03527,
    ),
    BUSAN_NEW_PORT_TIDE_OBS_CODE: TideStation(
        code=BUSAN_NEW_PORT_TIDE_OBS_CODE,
        name="부산항신항 조위관측소",
        lat=35.07750,
        lng=128.78472,
    ),
    GADEOKDO_TIDE_OBS_CODE: TideStation(
        code=GADEOKDO_TIDE_OBS_CODE,
        name="가덕도 조위관측소",
        lat=35.02417,
        lng=128.81093,
    ),
    ULSAN_TIDE_OBS_CODE: TideStation(
        code=ULSAN_TIDE_OBS_CODE,
        name="울산 조위관측소",
        lat=35.50194,
        lng=129.38722,
    ),
}

SPOTS: list[Spot] = [
    # ── 해수욕장 ──
    Spot(id="haeundae", name="해운대해수욕장", lat=35.1587, lng=129.1604,
         type=SpotType.BEACH, khoa_obs_code="TW_0062",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="gwangalli", name="광안리해수욕장", lat=35.1531, lng=129.1187,
         type=SpotType.BEACH, khoa_obs_code="TW_0062",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="songjeong", name="송정해수욕장", lat=35.1786, lng=129.2003,
         type=SpotType.BEACH, khoa_obs_code="TW_0090",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="songdo", name="송도해수욕장", lat=35.0759, lng=129.0169,
         type=SpotType.BEACH, khoa_obs_code="TW_0087",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="dadaepo", name="다대포해수욕장", lat=35.0489, lng=128.9664,
         type=SpotType.BEACH, khoa_obs_code="TW_0087",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="ilgwang", name="일광해수욕장", lat=35.2617, lng=129.2360,
         type=SpotType.BEACH, khoa_obs_code="TW_0092",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="imnang", name="임랑해수욕장", lat=35.3213, lng=129.2665,
         type=SpotType.BEACH, khoa_obs_code="TW_0092",
         khoa_tide_obs_code=ULSAN_TIDE_OBS_CODE, kma_area="부산"),
    # ── 항 ──
    Spot(id="busanhang", name="부산항", lat=35.0966, lng=129.0353,
         type=SpotType.PORT, khoa_obs_code="TW_0087",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="gamcheon", name="감천항", lat=35.0778, lng=129.0136,
         type=SpotType.PORT, khoa_obs_code="TW_0087",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="daebyeon", name="대변항", lat=35.2445, lng=129.2245,
         type=SpotType.PORT, khoa_obs_code="TW_0090",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="dadaepohang", name="다대포항", lat=35.0475, lng=128.9700,
         type=SpotType.PORT, khoa_obs_code="TW_0087",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    # ── 갯바위 ──
    Spot(id="taejongdae", name="태종대", lat=35.0517, lng=129.0870,
         type=SpotType.ROCK, khoa_obs_code="TW_0087",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="oryukdo", name="오륙도", lat=35.0975, lng=129.1236,
         type=SpotType.ROCK, khoa_obs_code="TW_0087",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="cheongsapo", name="청사포", lat=35.1611, lng=129.1897,
         type=SpotType.ROCK, khoa_obs_code="TW_0062",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
    Spot(id="igidae", name="이기대", lat=35.1225, lng=129.1225,
         type=SpotType.ROCK, khoa_obs_code="TW_0087",
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
]

_BY_ID = {s.id: s for s in SPOTS}
_BY_NAME = {s.name: s for s in SPOTS}


def all_spots() -> list[Spot]:
    return list(SPOTS)


def get_spot(key: str) -> Spot | None:
    """id 또는 한글 이름으로 조회."""
    return _BY_ID.get(key) or _BY_NAME.get(key)


def tide_reference_for(spot: Spot) -> tuple[TideStation, float] | None:
    """연결한 조위관측소와 서비스 지점까지의 직선거리(km)를 반환한다."""
    station = TIDE_STATIONS.get(spot.khoa_tide_obs_code or "")
    if station is None:
        return None
    return station, _tide_distance_km(spot, station)


def nearest_tide_reference_for(spot: Spot) -> tuple[TideStation, float]:
    """등록한 부산권·경계 인접 관측소 중 직선거리가 가장 짧은 관측소를 반환한다."""
    return min(
        ((station, _tide_distance_km(spot, station)) for station in TIDE_STATIONS.values()),
        key=lambda reference: reference[1],
    )


def _tide_distance_km(spot: Spot, station: TideStation) -> float:
    lat1, lng1, lat2, lng2 = map(radians, (spot.lat, spot.lng, station.lat, station.lng))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return round(2 * 6371.0 * asin(sqrt(a)), 1)
