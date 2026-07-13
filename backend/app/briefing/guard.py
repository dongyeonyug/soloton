"""런타임 가드 (AC6) — LLM 산문 영역에 무허용 숫자 토큰이 있으면 폐기.

핵심 불변식: LLM 은 어떤 수치도 생성하지 않는다. 모든 숫자는 코드 슬롯필이 소유하므로,
'LLM 영역에 숫자 0개' 는 인용 정확성의 자명한 증명이다. 위반 시 산문을 버리고
템플릿/자백으로 폴백한다(generate.py). CI(test_llm_region_numberfree)와 런타임 이중 게이트.

응급 전화번호(119 등) 같은 정당한 숫자도 LLM 이 아니라 템플릿(코드)이 소유한다 →
LLM 영역은 순수하게 숫자 0개를 요구한다.
"""

from __future__ import annotations

import re

# 아라비아/전각 숫자. 발견 시 위반(허용목록 비어있음). 소수점·자릿점(전각 포함)으로 이어진
# 숫자는 한 토큰으로 묶는다 — 탐지 기준은 그대로(숫자 1개라도 있으면 위반)이고, 시연 화면에서
# "1.5" 가 "1"·"5" 로 쪼개져 보이지 않게 하기 위한 것이다.
_DIGIT_RE = re.compile(r"[0-9０-９]+(?:[.,．，][0-9０-９]+)*")

# 방어적 추가: 한글 수사 + 측정단위 조합(예 "약 이 미터", "삼 미터")
_SPELLED_MEASURE_RE = re.compile(
    r"(영|일|이|삼|사|오|육|칠|팔|구|십|백|천)\s*(미터|미\b|센티|도|퍼센트|프로|노트|급)"
)

# E2(시간대 안내) 대비: 한글로 쓴 '시각'을 차단한다. 시각은 엔진이 계산하고 코드
# 템플릿 슬롯이 소유하므로, LLM 산문에 등장하면 위반이다. 아라비아 시각("3시")은
# 위 _DIGIT_RE 가 이미 잡는다.
#
# 오탐 방지가 핵심: "무리한 시도"(한 시), "이 시점"(이 시), "모두 시작"(두 시)처럼
# 정상 산문에 '숫자어+시'가 부분문자열로 흔히 들어간다. 그래서 단독 '숫자+시'는
# 잡지 않고, 시각임이 명확한 두 형태만 잡는다:
#   (a) 기간표지 + 숫자 + (시|시간|분)   예: "오후 세 시", "새벽 한 시"
#   (b) 숫자 + 시 + 근접표지            예: "세 시쯤", "다섯 시경", "두 시 정각"
_TIME_NUM = "영|일|이|삼|사|오|육|칠|팔|구|십|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열두|열한|열"
_TIME_PERIOD = "오전|오후|새벽|아침|점심|정오|저녁|밤중|밤|자정|낮"
_SPELLED_TIME_RE = re.compile(
    rf"(?:{_TIME_PERIOD})\s*(?:{_TIME_NUM})\s*(?:시간|시|분)"
    rf"|(?:{_TIME_NUM})\s*시\s*(?:경|쯤|께|무렵|정각)"
)


# 판정 규칙은 이 세 개가 전부다. 스팬/토큰 API 모두 여기서만 파생된다(단일 출처).
_RULES = (_DIGIT_RE, _SPELLED_MEASURE_RE, _SPELLED_TIME_RE)


def find_violation_spans(text: str) -> list[tuple[int, int]]:
    """위반 토큰의 (시작, 끝) 문자 오프셋. 겹치거나 맞닿은 구간은 병합한다.

    E1 시연 UI 가 원문 위에 위반 부분을 표시하는 데 쓴다. 판정 규칙은 아래
    find_number_violations 와 동일한 _RULES 이므로 화면과 런타임 가드가 갈라질 수 없다.
    """
    spans: list[tuple[int, int]] = []
    for rule in _RULES:
        spans.extend((m.start(), m.end()) for m in rule.finditer(text))
    spans.sort()

    merged: list[tuple[int, int]] = []
    for start, end in spans:
        # 규칙끼리 같은 글자를 겹쳐 잡은 경우만 합친다. 맞닿기만 한 구간("오후 두 시" + "3")은
        # 서로 다른 위반이므로 합치지 않는다 — 합치면 화면의 위반 건수가 실제보다 줄어든다.
        if merged and start < merged[-1][1]:
            prev_start, prev_end = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def find_number_violations(text: str) -> list[str]:
    """산문에서 무허용 숫자 토큰 목록. 비어있으면 통과."""
    return [text[start:end] for start, end in find_violation_spans(text)]


def is_number_free(text: str) -> bool:
    return not find_number_violations(text)
