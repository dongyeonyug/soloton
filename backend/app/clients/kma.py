"""기상청 기상특보 조회서비스(getPwnStatus) 클라이언트.

이 API는 전국 특보 현황을 반환하며 실측 풍속을 제공하지 않는다(advisory only).
실제 응답(2026-07-11 검증)의 현재 특보는 ``t6`` 필드에 다음 형식으로 담긴다:

    o 풍랑경보 : 남해동부바깥먼바다, 제주도앞바다, ...
    o 풍랑주의보 : 서해남부..., 남해동부안쪽먼바다, ...
    o 폭염경보 : ... 부산(부산서부) ...     ← 육상 특보(해양 무관)

따라서 "부산" 문자열이 응답 어딘가에 있다고 해서 그 특보가 부산 연안 풍랑특보인 것이
아니다(위 폭염경보처럼 육상일 수 있다). 각 특보 세그먼트의 지역 목록에 **부산 연안
앞바다 예보구역**이 포함될 때만 그 특보를 부산에 귀속한다.
"""

from __future__ import annotations

import re
from typing import Any

from ..models import AdvisoryKind
from ..spots import Spot
from .base import fetch_json

KMA_URL = "https://apis.data.go.kr/1360000/WthrWrnInfoService/getPwnStatus"

# 부산 연안(앞바다) 해상 예보구역. 부산·울산 연안은 '남해동부앞바다'에 속한다.
# 먼바다(안쪽/바깥먼바다)는 연안 지점에 해당하지 않으므로 제외한다.
BUSAN_SEA_ZONES: tuple[str, ...] = ("남해동부앞바다", "부산앞바다", "부산남부앞바다")

# 풍랑/풍파 특보만 위험도에 반영(육상 특보는 무시).
ADVISORY_MAP: dict[str, AdvisoryKind] = {
    "풍랑경보": AdvisoryKind.WIND_WAVE_ALERT,
    "풍랑주의보": AdvisoryKind.WIND_WAVE_WARNING,
    "풍파경보": AdvisoryKind.WAVE_ALERT,
    "풍파주의보": AdvisoryKind.WAVE_WARNING,
}
ADVISORY_PRIORITY: dict[AdvisoryKind, int] = {
    AdvisoryKind.NONE: 0,
    AdvisoryKind.WIND_WAVE_WARNING: 1,
    AdvisoryKind.WAVE_WARNING: 1,
    AdvisoryKind.WIND_WAVE_ALERT: 2,
    AdvisoryKind.WAVE_ALERT: 2,
}


async def fetch_spot(spot: Spot, api_key: str) -> dict[str, Any] | None:
    """현재 기상특보 현황을 조회한다. 이 API는 관측 풍속을 제공하지 않는다."""
    if not api_key or not spot.kma_area:
        return None

    raw = await fetch_json(
        KMA_URL,
        params={
            "ServiceKey": api_key,
            "pageNo": 1,
            "numOfRows": 300,
            "dataType": "JSON",
        },
    )
    return _parse(raw, area=spot.kma_area) if raw is not None else None


def _parse(raw: Any, *, area: str) -> dict[str, Any] | None:
    """현재 특보(t6) 세그먼트를 구조적으로 파싱해 부산 연안 풍랑특보만 귀속한다."""
    items = _records(raw)
    if items is None:
        return None

    advisory = AdvisoryKind.NONE
    for item in items:
        if not isinstance(item, dict):
            continue
        current = str(item.get("t6", ""))  # t7=예비특보는 미반영(발효 전)
        for kind in _busan_sea_advisories(current):
            if ADVISORY_PRIORITY[kind] > ADVISORY_PRIORITY[advisory]:
                advisory = kind
    return {"advisory": advisory}


def _busan_sea_advisories(t6: str) -> list[AdvisoryKind]:
    """t6 를 'o <특보명> : <지역목록>' 세그먼트로 쪼개 부산 연안 풍랑특보만 추출."""
    found: list[AdvisoryKind] = []
    for segment in re.split(r"(?:^|\n)\s*o\s+", t6):
        head, sep, regions = segment.partition(":")
        if not sep:
            continue
        kind = next((k for text, k in ADVISORY_MAP.items() if text in head), None)
        if kind is None:
            continue
        if any(zone in regions for zone in BUSAN_SEA_ZONES):
            found.append(kind)
    return found


def _records(raw: Any) -> list[dict[str, Any]] | None:
    """특보현황 JSON의 표준 래퍼만 수용하고, 모르는 계약은 결측으로 보낸다."""
    try:
        items = raw["response"]["body"]["items"] if isinstance(raw, dict) else None
    except (KeyError, TypeError):
        return None
    if isinstance(items, dict) and "item" in items:
        items = items["item"]
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return None
