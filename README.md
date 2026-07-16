# 🌊 오늘의 바다 (Today's Sea)

**환각 없는 AI 연안 해양안전 브리핑 웹서비스.** 부산 핵심 연안 지점의 공공 해양데이터를 통합해, **코드가 결정론적으로 위험도 등급(안전/주의/위험)을 확정**하고 Claude는 그 확정값을 **숫자를 스스로 만들지 않는 산문**으로만 표현합니다. 결측은 추정하지 않고 '정보없음'으로 자백합니다.

> BIPA 「나는 Solo AI」 공모전 출품작 · 1인 · MIT

## 왜 무환각인가
숫자는 **코드가 보장**하고, AI는 **사람이 읽을 판단으로 번역**만 합니다. 브리핑의 모든 수치·등급은 코드 슬롯필 계층이 소유하며(구조적 인용), LLM 산문은 수집 배치에서만 만들고 공개 요청은 저장분을 다시 가드로 확인하거나 코드 안내로 폴백합니다. 산문 상태도 `검증 통과`·`가드 차단`·`생성 불가`·`코드 폴백`으로 함께 제공합니다. 자세한 내용은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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

## Render 무료 서버 깨우기
`.github/workflows/render-wakeup.yml`이 10분마다 Render 백엔드의 `/api/health`를 호출합니다.

GitHub 저장소의 **Settings → Secrets and variables → Actions → New repository secret**에서
`RENDER_WAKE_URL`을 추가하세요.

예시:
```text
https://oneul-ui-bada-api.onrender.com/api/health
```

설정 후 GitHub Actions의 **Render wakeup** 워크플로우를 수동 실행하면 바로 확인할 수 있습니다.

## 배포 연결
1. Render에서 이 저장소의 `render.yaml`로 백엔드를 배포한다. `USE_SNAPSHOT_ONLY=1`은 유지하고, Vercel 운영 주소가 정해지면 `FRONTEND_ORIGIN=https://<project>.vercel.app`로 설정한다. 별도의 미리보기 주소도 실제 API를 호출해야 한다면 쉼표로 함께 추가한다.
2. Vercel에서 Root Directory를 `frontend`로 지정하고 환경변수 `VITE_API_BASE=https://oneul-ui-bada-api.onrender.com`를 넣는다.
3. Vercel 재배포 후 Vercel 홈 화면에서 지점 목록이 표시되는지 확인한다. Render의 `/api/health` 응답에서 `snapshot_only: true`, `spot_count: 15`를 확인한다.

`VITE_API_BASE` 또는 `FRONTEND_ORIGIN` 중 하나라도 비어 있으면 브라우저에서 API 요청이 실패할 수 있다. `FRONTEND_ORIGIN`에는 신뢰하는 주소만 쉼표로 추가하며, 전체 Vercel 도메인을 열어 두지 않는다. 실제 도메인이 다르면 위 예시의 Render URL만 해당 서비스 URL로 바꾼다.

## 데이터 출처
Phase 2 소스는 KHOA **해양관측부이 최신 관측데이터**(`15155516`, 실측), KHOA **조위관측소 최신 관측데이터**(`15155508`, 조위), 기상청 **기상특보 조회서비스**(`15000415`, 공식 특보)입니다. `DATA_PROVIDER=auto`는 KHOA/KMA 키가 있으면 **하이브리드**를 선택합니다 — KHOA 실측을 우선하고, 파고·풍속 센서가 없는 부이(예: 부산항 `TW_0087`)의 지점은 Open-Meteo 예보값으로 백필하며 지표별 출처(실측/예보)를 명시합니다. 조위 키는 `KHOA_TIDE_API_KEY`에 넣고, 비워두면 `KHOA_API_KEY`를 재사용합니다. 상세는 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## ⚠️ 면책
본 서비스는 **참고용**이며 실제 해안 활동 여부의 공식 근거가 아닙니다. [docs/DISCLAIMER.md](docs/DISCLAIMER.md).

## 라이선스
[MIT](LICENSE)
