"""숫자 금지 프롬프트 빌더. LLM 은 등급/맥락(라벨)만 받아 활동별 조언 산문을 쓴다.

절대 수치를 주지 않는다 — 값이 프롬프트에 없으면 LLM 이 인용할 수도 없다(구조적 차단).
"""

from __future__ import annotations

from ..models import RiskGrade
from ..spots import Spot

SYSTEM_PROMPT = (
    "당신은 한국 연안 해양안전 조언자입니다. "
    "규칙: (1) 어떤 숫자·수치·측정값도 절대 쓰지 마세요(아라비아 숫자, 한글 수사 모두 금지). "
    "수치는 이미 화면에 코드가 표시합니다. (2) 위험도 등급과 활동만 근거로 "
    "사람이 읽기 쉬운 2~3문장의 조언을 한국어로 쓰세요. (3) 없는 정보를 지어내지 마세요. "
    "(4) 담백하고 신뢰감 있게, 겁주지 않되 위험은 분명히 전하세요."
)


def build_user_prompt(spot: Spot, risk: RiskGrade) -> str:
    missing = [bv.label for bv in risk.basis_values if bv.is_missing]
    advisories = [a.kind.value for a in risk.basis_advisories]
    lines = [
        f"지점: {spot.name} ({spot.type.value})",
        f"시간대: {risk.time_slot}",
        f"활동: {risk.activity.value}",
        f"확정 위험도 등급: {risk.grade.label_ko}",
        f"발효 특보: {', '.join(advisories) if advisories else '없음'}",
    ]
    if missing:
        lines.append(f"관측 정보없음 지표: {', '.join(missing)} (이 지표는 값을 언급하지 말고, 정보가 없다는 사실만 반영)")
    lines.append(
        "위 맥락으로 이 활동을 하려는 사람에게 줄 조언을 쓰세요. 수치는 절대 쓰지 마세요."
    )
    return "\n".join(lines)
