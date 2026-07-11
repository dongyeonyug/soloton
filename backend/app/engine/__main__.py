"""CLI: python -m app.engine <spot> [activity] — 지점 위험도 확인(W1 검증)."""

from __future__ import annotations

import sys

from ..models import Activity
from ..service import brief_spot, evaluate_spot, resolve_spot


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m app.engine <spot_id|이름> [조업|레저|갯바위|물놀이]")
        print("예: python -m app.engine 송정해수욕장 물놀이")
        return 2
    spot = resolve_spot(argv[0])
    if spot is None:
        print(f"알 수 없는 지점: {argv[0]}")
        return 1
    activity = Activity(argv[1]) if len(argv) > 1 else Activity.LEISURE

    risk, as_of = evaluate_spot(spot, activity)
    briefing = brief_spot(spot, activity)
    print(f"■ {spot.name} / {activity.value} / as_of {as_of}")
    print(f"  등급: {risk.grade.label_ko} ({risk.grade.value})  "
          f"결측임계={risk.has_missing_critical}")
    print(f"  근거: {briefing.template_text}")
    print(f"  브리핑: {briefing.llm_prose}  (llm_used={briefing.llm_used})")
    for rec in briefing.recommendations:
        print(f"   - {rec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
