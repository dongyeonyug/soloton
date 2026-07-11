# 🌊 오늘의 바다 (Today's Sea)

**환각 없는 AI 연안 해양안전 브리핑 웹서비스.** 부산 핵심 연안 지점의 공공 해양데이터를 통합해, **코드가 결정론적으로 위험도 등급(안전/주의/위험)을 확정**하고 Claude는 그 확정값을 **숫자를 스스로 만들지 않는 산문**으로만 표현합니다. 결측은 추정하지 않고 '정보없음'으로 자백합니다.

> BIPA 「나는 Solo AI」 공모전 출품작 · 1인 · MIT

## 왜 무환각인가
숫자는 **코드가 보장**하고, AI는 **사람이 읽을 판단으로 번역**만 합니다. 브리핑의 모든 수치·등급은 코드 슬롯필 계층이 소유하며(구조적 인용), LLM은 숫자 없는 활동별 조언 산문만 생성합니다. 런타임 가드가 산문에서 무허용 숫자를 발견하면 즉시 템플릿으로 폴백합니다. 자세한 내용은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 구조
```
backend/   FastAPI + 결정론 규칙엔진 + 슬롯필 브리핑 + Claude
frontend/  React + Vite + TS + Leaflet (지도→신호등→근거 브리핑 3뷰)
docs/      ARCHITECTURE · RISK_THRESHOLDS · DATA_SOURCES · DISCLAIMER
```

## 빠른 시작 (backend)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env      # 인증키 없으면 USE_SNAPSHOT_ONLY=1 로 스냅샷 서빙
pytest                          # 전 AC 게이트 검증
python -m app.engine 송정해수욕장   # CLI 위험도 확인
# .env에 공공데이터 키 입력 후 Phase 2 스냅샷 갱신
python -m app.ingest.collect
uvicorn app.main:app --reload
```

## 데이터 출처
Phase 2 소스는 KHOA **해양관측부이 최신 관측데이터**(`15155516`, 실측), KHOA **조위관측소 최신 관측데이터**(`15155508`, 조위), 기상청 **기상특보 조회서비스**(`15000415`, 공식 특보)입니다. `DATA_PROVIDER=auto`는 KHOA/KMA 키가 있으면 **하이브리드**를 선택합니다 — KHOA 실측을 우선하고, 파고·풍속 센서가 없는 부이(예: 부산항 `TW_0087`)의 지점은 Open-Meteo 예보값으로 백필하며 지표별 출처(실측/예보)를 명시합니다. 조위 키는 `KHOA_TIDE_API_KEY`에 넣고, 비워두면 `KHOA_API_KEY`를 재사용합니다. 상세는 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## ⚠️ 면책
본 서비스는 **참고용**이며 실제 항해·조업·입수 판단의 공식 근거가 아닙니다. [docs/DISCLAIMER.md](docs/DISCLAIMER.md).

## 라이선스
[MIT](LICENSE)
