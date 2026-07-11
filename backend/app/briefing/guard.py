"""런타임 가드 (AC6) — LLM 산문 영역에 무허용 숫자 토큰이 있으면 폐기.

핵심 불변식: LLM 은 어떤 수치도 생성하지 않는다. 모든 숫자는 코드 슬롯필이 소유하므로,
'LLM 영역에 숫자 0개' 는 인용 정확성의 자명한 증명이다. 위반 시 산문을 버리고
템플릿/자백으로 폴백한다(generate.py). CI(test_llm_region_numberfree)와 런타임 이중 게이트.

응급 전화번호(119 등) 같은 정당한 숫자도 LLM 이 아니라 템플릿(코드)이 소유한다 →
LLM 영역은 순수하게 숫자 0개를 요구한다.
"""

from __future__ import annotations

import re

# 아라비아/전각 숫자. 발견 시 위반(허용목록 비어있음).
_DIGIT_RE = re.compile(r"[0-9０-９]")

# 방어적 추가: 한글 수사 + 측정단위 조합(예 "약 이 미터", "삼 미터")
_SPELLED_MEASURE_RE = re.compile(
    r"(영|일|이|삼|사|오|육|칠|팔|구|십|백|천)\s*(미터|미\b|센티|도|퍼센트|프로|노트|급)"
)


def find_number_violations(text: str) -> list[str]:
    """산문에서 무허용 숫자 토큰 목록. 비어있으면 통과."""
    violations = _DIGIT_RE.findall(text)
    violations += ["".join(m) for m in _SPELLED_MEASURE_RE.findall(text)]
    return violations


def is_number_free(text: str) -> bool:
    return not find_number_violations(text)
