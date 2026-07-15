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

from dataclasses import dataclass
from datetime import date
import re
from typing import Any

from ..models import AdvisoryKind
from ..spots import Spot
from .base import fetch_json

KMA_URL = "https://apis.data.go.kr/1360000/WthrWrnInfoService/getPwnStatus"
KMA_WARNING_LIST_URL = "https://apis.data.go.kr/1360000/WthrWrnInfoService/getWthrWrnList"

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


@dataclass(frozen=True)
class WarningListRecord:
    """기상청 기상특보목록의 최소 보존 필드.

    목록은 특보의 발표 이력이며, 개별 해안 지점에 실제 발효됐다는 증거는 아니다.
    현재 서비스의 해역 귀속 판단은 ``getPwnStatus``의 ``t6`` 구조 파서가 계속 맡는다.
    """

    stn_id: str
    tm_fc: str
    tm_seq: int
    title: str

    @property
    def key(self) -> tuple[str, str, int]:
        return self.stn_id, self.tm_fc, self.tm_seq


@dataclass(frozen=True)
class CoastalAdvisorySegment:
    """현재 특보 원문에서 부산 연안에 실제로 매칭된 세그먼트."""

    advisory: AdvisoryKind
    advisory_name: str
    regions: tuple[str, ...]
    matched_zones: tuple[str, ...]

    def as_history_dict(self) -> dict[str, Any]:
        return {
            "advisory": self.advisory.value,
            "advisory_name": self.advisory_name,
            "regions": list(self.regions),
            "matched_zones": list(self.matched_zones),
        }


@dataclass(frozen=True)
class CoastalAdvisoryScope:
    """현재 특보 원문과 그 중 부산 연안에 귀속된 결과."""

    advisory: AdvisoryKind
    source_t6: str
    matched_segments: tuple[CoastalAdvisorySegment, ...]


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


async def fetch_busan_coastal_scope(api_key: str) -> CoastalAdvisoryScope | None:
    """현재 특보에서 부산 연안 적용 근거를 보존 가능한 형태로 읽는다.

    이 함수는 특보 발표 목록과 별개로, 수집 당시 ``t6`` 원문과 구조적 해역 매칭
    결과를 함께 돌려준다. 실패는 ``None``으로 표기해 기존 보존 원장을 덮어쓰지
    않도록 호출측에 맡긴다.
    """
    if not api_key:
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
    return _parse_coastal_scope(raw)


async def fetch_warning_list(
    api_key: str,
    *,
    from_date: date,
    to_date: date,
    station_id: str,
) -> list[WarningListRecord] | None:
    """발표 기간 내 공식 특보 목록을 읽는다.

    목록 API가 오류를 반환하거나 계약이 달라지면 ``None``을 반환한다. 호출측은 그
    경우 기존 보존 원장을 유지해야 하며, 빈 목록(`[]`)과 실패를 구분한다.
    """
    if not api_key:
        return None
    raw = await fetch_json(
        KMA_WARNING_LIST_URL,
        params={
            "ServiceKey": api_key,
            "pageNo": 1,
            "numOfRows": 1000,
            "dataType": "JSON",
            "stnId": station_id,
            "fromTmFc": from_date.strftime("%Y%m%d"),
            "toTmFc": to_date.strftime("%Y%m%d"),
        },
    )
    return _parse_warning_list(raw)


def _parse(raw: Any, *, area: str) -> dict[str, Any] | None:
    """현재 특보(t6) 세그먼트를 구조적으로 파싱해 부산 연안 풍랑특보만 귀속한다."""
    scope = _parse_coastal_scope(raw)
    if scope is None:
        return None
    return {"advisory": scope.advisory}


def _parse_coastal_scope(raw: Any) -> CoastalAdvisoryScope | None:
    """현재 특보의 원문과 부산 연안 귀속 결과를 함께 정규화한다."""
    items = _records(raw)
    if items is None:
        return None

    advisory = AdvisoryKind.NONE
    source_t6: list[str] = []
    matched_segments: list[CoastalAdvisorySegment] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        current = item.get("t6", "")  # t7=예비특보는 미반영(발효 전)
        current = current if isinstance(current, str) else ""
        source_t6.append(current)
        for segment in _busan_sea_advisory_segments(current):
            matched_segments.append(segment)
            if ADVISORY_PRIORITY[segment.advisory] > ADVISORY_PRIORITY[advisory]:
                advisory = segment.advisory
    return CoastalAdvisoryScope(
        advisory=advisory,
        source_t6="\n\n".join(source_t6),
        matched_segments=tuple(matched_segments),
    )


def _busan_sea_advisories(t6: str) -> list[AdvisoryKind]:
    """t6 를 'o <특보명> : <지역목록>' 세그먼트로 쪼개 부산 연안 풍랑특보만 추출."""
    return [segment.advisory for segment in _busan_sea_advisory_segments(t6)]


def _busan_sea_advisory_segments(t6: str) -> list[CoastalAdvisorySegment]:
    """부산 연안 구역이 들어간 풍랑/풍파 특보 세그먼트와 매칭 근거를 추출한다."""
    found: list[CoastalAdvisorySegment] = []
    for segment in re.split(r"(?:^|\n)\s*o\s+", t6):
        head, sep, regions = segment.partition(":")
        if not sep:
            continue
        match = next(((text, kind) for text, kind in ADVISORY_MAP.items() if text in head), None)
        if match is None:
            continue
        advisory_name, kind = match
        matched_zones = tuple(zone for zone in BUSAN_SEA_ZONES if zone in regions)
        if not matched_zones:
            continue
        found.append(
            CoastalAdvisorySegment(
                advisory=kind,
                advisory_name=advisory_name,
                regions=tuple(part.strip() for part in regions.split(",") if part.strip()),
                matched_zones=matched_zones,
            )
        )
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


def _parse_warning_list(raw: Any) -> list[WarningListRecord] | None:
    """특보목록 응답을 보존 가능한 최소 레코드로 정규화한다."""
    try:
        response = raw["response"]
        header = response["header"]
        if str(header.get("resultCode")) != "00":
            return None
        items = response["body"].get("items")
    except (AttributeError, KeyError, TypeError):
        return None
    if items in (None, ""):
        return []
    if isinstance(items, dict):
        items = items.get("item", items)
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return None

    records: list[WarningListRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            stn_id = str(item["stnId"])
            tm_fc = str(item["tmFc"])
            tm_seq = int(item["tmSeq"])
            title = str(item["title"])
        except (KeyError, TypeError, ValueError):
            continue
        if stn_id and tm_fc and title:
            records.append(WarningListRecord(stn_id, tm_fc, tm_seq, title))
    return records
