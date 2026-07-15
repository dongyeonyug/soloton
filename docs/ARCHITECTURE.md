# 아키텍처 (ARCHITECTURE)

## 핵심 불변식
> **코드가 사실의 원천, LLM은 표현만.** 브리핑의 모든 수치·등급은 코드 슬롯필 계층이 소유하고, LLM은 숫자 없는 산문만 생성한다. 인용 검증은 사후 대조가 아니라 "LLM 영역에 숫자 0개"라는 **구조적 불변식**으로 증명된다.

## 데이터 흐름
```
공공 API (KHOA/KMA)                       [best-effort, W0 게이트]
      │  clients/ (retry·timeout·fail→missing)
      ▼
ingest/normalize → MarineObservation[]     per-metric observed_at·is_missing
      │  ingest/collect → snapshot.json + advisory_history.json (발표·해역귀속, GH Actions commit-back)
      │                    └─ 배치 내 KMA 1회·KHOA 관측소별 요청 공유
      │  시간별 예보: 수집 상태·실패 원인·수집 시각 보존
      ▼
engine/thresholds + engine/risk            순수·결정론·근거 성격 → RiskGrade + decision_steps
engine/forecast                            시간대 선택 또는 계산 불가 사유 → SafeWindowAssessment
      │  결측 임계지표 → 안전불가, CAUTION floor
      ▼
briefing/template  → BriefingSlots         코드가 수치·출처·시각 슬롯 채움(구조적 인용)
briefing/prompt    → 숫자금지 프롬프트
ingest/collect     → 배치에서만 Claude 산문 생성 (지점별 제한 시간, 순차 처리)
snapshot.json(v2)  → 산문 + 상태(verified/blocked_by_guard/generation_unavailable)
briefing/guard     → 저장 산문 재검증, 숫자 토큰 발견 시 폐기 → 코드 폴백
      ▼
routers/ (FastAPI) → JSON → frontend 3뷰 (지도→신호등→근거 브리핑)
```

## 계층 책임
- **clients**: 외부 API I/O 격리. 실패는 예외 대신 `is_missing` 플래그로 흡수.
- **ingest**: 원 응답 → 정규화 스키마. 배치 산문 생성·상태 기록, 스냅샷 직렬화/로드. 시간별 예보는 성공·빈 응답·시간 초과·소스 장애를 별도 기록한다.
- **engine**: 부작용 없는 순수함수. 등급 결정의 유일한 권위이며, 파고·풍속의 보수 매핑, 실제 기상특보의 공식 상향, 결측 보수화·최종 합산을 `decision_steps`로 남긴다. 조류는 지역 검증 임계값 전까지 수치·출처만 보이는 참고값으로 분리한다. 시간대 엔진은 선택 결과뿐 아니라 예보 부재·불완전·전 시간 위험의 사유도 `safe_window_assessment`로 남긴다.
- **briefing**: 슬롯필(코드 소유 수치) + 저장 산문 재검증 + 코드 폴백. 공개 요청에서 LLM 호출 없음.
- **routers**: HTTP 경계. 얇게.

## 배포
- Backend → Render (uvicorn). Frontend → Vercel (`VITE_API_BASE`).
- 데이터 신선도는 GH Actions commit-back 스냅샷이 주 경로. Render in-process 수집은 best-effort 부가.

## 무환각 보증의 4중 방어
1. **구조**: 슬롯필이 수치 소유, LLM은 산문만 (D4-B).
2. **배치 격리**: LLM 생성은 수집 배치에서만 수행하고, 공개 요청은 스냅샷만 읽는다.
3. **런타임**: `guard.py` 가 저장 산문을 다시 검사해 무허용 숫자 탐지 시 폴백한다.
4. **CI**: `test_llm_region_numberfree`, `test_prebake`, `test_slot_binding`, `test_missing_grade`, `test_confession`, `test_gold` 게이트.
