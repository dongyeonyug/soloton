# 아키텍처 (ARCHITECTURE)

## 핵심 불변식
> **코드가 사실의 원천, LLM은 표현만.** 브리핑의 모든 수치·등급은 코드 슬롯필 계층이 소유하고, LLM은 숫자 없는 산문만 생성한다. 인용 검증은 사후 대조가 아니라 "LLM 영역에 숫자 0개"라는 **구조적 불변식**으로 증명된다.

## 데이터 흐름
```
공공 API (KHOA/KMA)                       [best-effort, W0 게이트]
      │  clients/ (retry·timeout·fail→missing)
      ▼
ingest/normalize → MarineObservation[]     per-metric observed_at·is_missing
      │  ingest/collect → snapshot.json (GH Actions commit-back)
      ▼
engine/thresholds + engine/risk            순수·결정론·sourced → RiskGrade
      │  결측 임계지표 → 안전불가, CAUTION floor
      ▼
briefing/template  → BriefingSlots         코드가 수치·출처·시각 슬롯 채움(구조적 인용)
briefing/prompt    → 숫자금지 프롬프트
briefing/generate  → Claude 산문 (활동별 조언)
briefing/guard     → 숫자 토큰 발견 시 산문 폐기 → 템플릿 폴백    [런타임 가드]
      ▼
routers/ (FastAPI) → JSON → frontend 3뷰 (지도→신호등→근거 브리핑)
```

## 계층 책임
- **clients**: 외부 API I/O 격리. 실패는 예외 대신 `is_missing` 플래그로 흡수.
- **ingest**: 원 응답 → 정규화 스키마. 스냅샷 직렬화/로드.
- **engine**: 부작용 없는 순수함수. 등급 결정의 유일한 권위.
- **briefing**: 슬롯필(코드 소유 수치) + LLM 산문(숫자 없음) + 런타임 가드.
- **routers**: HTTP 경계. 얇게.

## 배포
- Backend → Render (uvicorn). Frontend → Vercel (`VITE_API_BASE`).
- 데이터 신선도는 GH Actions commit-back 스냅샷이 주 경로. Render in-process 수집은 best-effort 부가.

## 무환각 보증의 3중 방어
1. **구조**: 슬롯필이 수치 소유, LLM은 산문만 (D4-B).
2. **런타임**: `guard.py` 가 산문의 무허용 숫자 탐지 → 폴백.
3. **CI**: `test_llm_region_numberfree`, `test_slot_binding`, `test_missing_grade`, `test_confession`, `test_gold` 게이트.
