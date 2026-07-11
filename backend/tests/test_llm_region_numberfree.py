"""AC6: LLM 산문 영역 숫자 토큰 0개 — 런타임 가드 + 폴백.

가드가 숫자 섞인 산문을 폐기하고, 서빙되는 llm_prose 는 항상 number-free 임을 보장.
"""

import pytest

from app.briefing import guard
from app.models import Activity
from app.service import brief_spot
from app.spots import all_spots


# ── guard 단위 ──
def test_guard_flags_arabic_digits():
    assert not guard.is_number_free("파고가 2미터입니다")
    assert guard.find_number_violations("바람 15m/s")


def test_guard_flags_fullwidth_and_spelled():
    assert not guard.is_number_free("약 ３미터")
    assert not guard.is_number_free("약 이 미터 정도")


def test_guard_passes_clean_prose():
    assert guard.is_number_free("바람이 강하니 입수를 삼가세요.")


# ── 런타임 폴백 ──
def _llm_with_numbers(system, user):
    return "현재 파고는 2.3m이고 바람은 15m/s로 위험합니다."  # 숫자 유출 시도


def _llm_clean(system, user):
    return "지금은 바다 상황이 좋지 않으니 활동을 미루는 편이 좋겠습니다."


def test_number_laden_prose_rejected_and_fallback():
    spot = all_spots()[0]
    briefing = brief_spot(spot, Activity.FISHING, llm_fn=_llm_with_numbers)
    assert briefing.llm_used is False          # 가드가 폐기
    assert guard.is_number_free(briefing.llm_prose)  # 폴백은 number-free


def test_clean_prose_accepted():
    spot = all_spots()[0]
    briefing = brief_spot(spot, Activity.FISHING, llm_fn=_llm_clean)
    assert briefing.llm_used is True
    assert guard.is_number_free(briefing.llm_prose)


@pytest.mark.parametrize("spot", all_spots(), ids=[s.id for s in all_spots()])
def test_all_spots_served_prose_numberfree(spot):
    """어떤 지점·활동이든 서빙되는 산문은 숫자 0개(런타임+폴백 이중)."""
    for activity in Activity:
        briefing = brief_spot(spot, activity, llm_fn=_llm_with_numbers)
        assert guard.is_number_free(briefing.llm_prose), (
            f"{spot.id}/{activity.value}: 산문에 숫자 유출"
        )
