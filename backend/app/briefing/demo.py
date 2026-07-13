"""E1 — '거짓말 차단'을 눈에 보이게 하는 시연 계층.

정직성 규칙 두 가지를 동시에 지킨다.

1. **입력은 재현된 예시다.** 아래 후보 문장들은 실제 LLM 이 뱉은 로그가 아니라, 흔한
   환각 유형(수치 날조·시각 날조·결측 추정)을 재현한 예시다. 화면도 그렇게 표기한다.
2. **판정은 진짜다.** 위반 토큰·폐기 여부·대체 산문은 하드코딩하지 않는다. 프로덕션이
   쓰는 것과 같은 `service.brief_spot` (→ `generate_briefing` → `guard`) 을 그대로 실행해
   그 결과를 보여준다. 가드를 고치면 이 시연의 판정도 같이 바뀐다.

따라서 이 시연은 '짜맞춘 데모'가 아니라 프로덕션 코드의 실행 결과다.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..ingest.cache import SnapshotDoc, get_snapshot
from ..models import Activity, Grade
from ..service import brief_spot, evaluate_spot
from ..spots import Spot
from . import guard


# 후보 문장 하나를 LLM 응답으로 주입하는 어댑터. brief_spot 의 llm_fn 자리에 꽂힌다.
def _canned_llm(text: str):
    def call(_system: str, _user: str) -> str:
        return text

    return call


class GuardVerdict(BaseModel):
    """산문 한 편에 대한 가드 판정 + 실제로 서빙될 결과."""

    text: str
    violations: list[str]
    violation_spans: list[tuple[int, int]]
    blocked: bool
    served_prose: str  # 폐기됐다면 코드 생성 폴백, 통과했다면 원문 그대로
    llm_used: bool


class GuardCase(GuardVerdict):
    """준비된 시나리오 = 재현한 환각 유형 + 그에 대한 실제 판정."""

    id: str
    title: str
    note: str


class GuardDemo(BaseModel):
    spot_id: str
    spot_name: str
    grade: Grade
    cases: list[GuardCase]


# 재현할 환각 유형. 문장은 예시지만 판정은 아래에서 실제 가드가 내린다.
_SCENARIOS: list[dict[str, str]] = [
    {
        "id": "invented-numbers",
        "title": "수치를 지어낸 경우",
        "note": "LLM 이 그럴듯한 파고·풍속을 만들어 쓰는 가장 흔한 환각입니다.",
        "text": (
            "오늘 이곳은 파고 0.5m로 잔잔하고 바람도 초속 4m 수준이라 "
            "물놀이하기 좋은 날입니다."
        ),
    },
    {
        "id": "invented-time",
        "title": "시각을 지어낸 경우",
        "note": "'언제 나가야 하나'를 묻는 순간 LLM 은 근거 없는 시각을 만들어냅니다.",
        "text": "오후 세 시쯤이면 물결이 잦아드니 그때 나가시길 권합니다.",
    },
    {
        "id": "estimated-missing",
        "title": "없는 값을 추정으로 메운 경우",
        "note": "관측이 결측일 때 '대략 이 정도'로 메우는 것도 거짓말입니다.",
        "text": "관측값이 확인되지 않지만 체감상 삼 미터 안팎의 너울이 있어 보입니다.",
    },
    {
        "id": "number-free",
        "title": "숫자 없이 표현만 한 경우",
        "note": "수치는 코드가 인용하고 AI 는 사람 말로 옮기기만 하면 그대로 서빙됩니다.",
        "text": (
            "지금은 활동하기에 무난한 편입니다. 다만 바람이 점차 강해질 수 있으니 "
            "상황을 살피며 여유를 두고 움직이세요."
        ),
    },
]


def check_prose(
    spot: Spot,
    text: str,
    *,
    doc: SnapshotDoc | None = None,
) -> GuardVerdict:
    """산문 한 편을 프로덕션 브리핑 경로에 그대로 태워 판정 결과를 돌려준다.

    `brief_spot` 에 llm_fn 으로 주입하므로, 이 지점의 실제 관측·등급 위에서
    런타임 가드가 돌고, 폐기 시 폴백까지 프로덕션과 동일하게 일어난다.

    `blocked` 는 여기서 다시 판단하지 않고 프로덕션 결과(`llm_used`)에서 역산한다.
    가드 밖에 폐기 조건이 하나 더 생기더라도 시연이 프로덕션과 어긋날 수 없게 하기 위함이다.
    스팬은 판정이 아니라 화면 하이라이트용이다.
    """
    briefing = brief_spot(
        spot,
        Activity.LEISURE,
        doc=doc,
        llm_fn=_canned_llm(text),
    )
    spans = guard.find_violation_spans(text)
    return GuardVerdict(
        text=text,
        violations=[text[s:e] for s, e in spans],
        violation_spans=spans,
        blocked=not briefing.llm_used,
        served_prose=briefing.llm_prose,
        llm_used=briefing.llm_used,
    )


def run_demo(spot: Spot, *, doc: SnapshotDoc | None = None) -> GuardDemo:
    """준비된 시나리오 전부를 실제 가드에 태운다."""
    doc = doc or get_snapshot()  # 시나리오들이 같은 스냅샷 위에서 판정되도록 한 번만 읽는다
    cases = [
        GuardCase(
            id=scenario["id"],
            title=scenario["title"],
            note=scenario["note"],
            **check_prose(spot, scenario["text"], doc=doc).model_dump(),
        )
        for scenario in _SCENARIOS
    ]
    risk, _ = evaluate_spot(spot, Activity.LEISURE, doc=doc)
    return GuardDemo(
        spot_id=spot.id,
        spot_name=spot.name,
        grade=risk.grade,
        cases=cases,
    )
