"""AC5b: 자백(브리핑) — 결측 주입 → is_confession=true, 결측 지표 수치 주장 없음."""

from app.models import Activity
from app.service import brief_spot, evaluate_spot
from app.briefing.template import MISSING_TEXT, render_template, build_slots
from app.spots import get_spot


def _fake_llm_clean(system, user):
    return "현재 여건을 신중히 살피고 안전 수칙을 지키세요."


def test_missing_spot_confesses():
    spot = get_spot("cheongsapo")  # 풍속 결측 시드
    briefing = brief_spot(spot, Activity.FISHING, llm_fn=_fake_llm_clean)
    assert briefing.is_confession is True


def test_missing_metric_shows_infoless_not_number():
    spot = get_spot("cheongsapo")
    risk, as_of = evaluate_spot(spot, Activity.FISHING)
    slots = build_slots(spot, risk, as_of)
    text = render_template(spot, risk, slots)
    # 결측 풍속은 '정보없음' 으로 자백, 조작된 수치 없음
    wind_slot = next(f for f in slots.filled_numbers if f.label == "풍속")
    assert wind_slot.is_missing is True
    assert wind_slot.value is None
    assert f"풍속 {MISSING_TEXT}" in text


def test_present_spot_not_confession():
    spot = get_spot("haeundae")  # 전 지표 present
    briefing = brief_spot(spot, Activity.SWIMMING, llm_fn=_fake_llm_clean)
    assert briefing.is_confession is False
