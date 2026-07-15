"""CLI: python -m app.engine <spot> — 지점 위험도 확인(W1 검증)."""

from __future__ import annotations

import sys

from ..service import brief_spot, evaluate_spot, resolve_spot


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m app.engine <spot_id|이름>")
        print("예: python -m app.engine 송정해수욕장")
        return 2
    spot = resolve_spot(argv[0])
    if spot is None:
        print(f"알 수 없는 지점: {argv[0]}")
        return 1
    risk, as_of = evaluate_spot(spot)
    briefing = brief_spot(spot)
    print(f"■ {spot.name} / 해안 활동 참고 / as_of {as_of}")
    print(f"  등급: {risk.grade.label_ko} ({risk.grade.value})  "
          f"결측임계={risk.has_missing_critical}")
    print(f"  근거: {briefing.template_text}")
    print(f"  브리핑: {briefing.llm_prose}  (prose_status={briefing.prose_status.value})")
    for rec in briefing.recommendations:
        print(f"   - {rec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
