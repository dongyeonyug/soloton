"""Phase 1 공식 확인 링크 레지스트리.

링크는 프런트에 흩어 두지 않는다. 활동·지역 범위, 소유자, 마지막 검증 시각과
대체 안내를 한 타입 계약으로 보존해 데이터가 없을 때도 공식 판단을 가장하도록
만들지 않는다.
"""

from __future__ import annotations

from datetime import datetime

from .models import OfficialLink, PlanActivity

_LAST_VERIFIED_AT = datetime(2026, 7, 17, 0, 0, 0)

_WATER_PLAY_LINKS: tuple[OfficialLink, ...] = (
    OfficialLink(
        label="기상청 해양기상 정보",
        url="https://www.weather.go.kr",
        source_owner="기상청",
        activity_scope=PlanActivity.WATER_PLAY,
        region_scope="부산 연안",
        last_verified_at=_LAST_VERIFIED_AT,
        fallback_text=(
            "기상청에서 부산 연안의 최신 특보와 해양예보를 다시 확인하세요."
        ),
    ),
    OfficialLink(
        label="해양경찰청 해양안전 정보",
        url="https://www.kcg.go.kr",
        source_owner="해양경찰청",
        activity_scope=PlanActivity.WATER_PLAY,
        region_scope="대한민국 연안",
        last_verified_at=_LAST_VERIFIED_AT,
        fallback_text=(
            "현장 통제와 긴급 상황은 해양경찰청 안내와 "
            "현장 안전요원의 지시를 따르세요."
        ),
    ),
)


def links_for(activity: PlanActivity) -> list[OfficialLink]:
    """호출자가 전역 레지스트리를 바꾸지 못하도록 링크 복사본을 돌려준다."""
    if activity is PlanActivity.WATER_PLAY:
        return [link.model_copy(deep=True) for link in _WATER_PLAY_LINKS]
    return []
