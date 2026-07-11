"""부산 핵심 연안 지점 (15). 좌표는 대표 지점 근사값.

``khoa_obs_code``는 국립해양조사원 해양관측부이 운영 현황의 부산권 부이 중
가장 가까운 관측소를 연결한다. 지점과 부이는 같은 위치가 아니며 거리 표는
``docs/DATA_SOURCES.md``에 기록한다. ``khoa_tide_obs_code``는 조위관측소 최신
관측데이터(`15155508`)용 코드다. 현재는 부산 대표 조위관측소 `DT_0005`로 시작하고,
실키 검증 후 서부권/동부권 세분화를 검토한다. ``kma_area``는 특보 제목의 지역 필터다.
"""

from __future__ import annotations

from .models import Spot, SpotType

BUSAN_TIDE_OBS_CODE = "DT_0005"

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
         khoa_tide_obs_code=BUSAN_TIDE_OBS_CODE, kma_area="부산"),
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
