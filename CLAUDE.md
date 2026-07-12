# Claude Code project context

Read [`.omc/handoffs/public-data-api-migration.md`](.omc/handoffs/public-data-api-migration.md) and [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) before changing the marine-data provider.

## Public-data API decision (2026-07-10)

- KHOA: data.go.kr `15155516`, `twRecent/GetTWRecentApiService`, key `KHOA_API_KEY`.
- KMA: data.go.kr `15000415`, `WthrWrnInfoService/getPwnStatus`, key `KMA_API_KEY`.
- Never commit `.env`, API keys, or unredacted live API responses.
- The retired `khoa.go.kr/api/oceangrid/tideObsPreTab` endpoint must not be restored.
- KMA `15000415` is advisory-only and must never be treated as a wind-speed source.
- Tide is now wired through optional KHOA `15155508` (`dtRecent/GetDTRecentApiService`). Use `KHOA_TIDE_API_KEY`, or leave it blank to reuse `KHOA_API_KEY`.

## Current implementation status

- New client URLs, official request parameters, defensive parsers, 부산-area warning filtering, and four official 부산-area buoy codes are implemented.
- Unit/regression tests use synthetic fixtures. After the user adds both keys to `.env`, run `cd backend && python -m app.ingest.collect` and validate redacted real responses before narrowing parser aliases.
- KHOA field names, units, observation timestamps, and sensor coverage still require live-response validation.
- KMA `getPwnStatus` parsing is conservative and unverified against a real response. Validate its structured sea-zone fields with the issued key before claiming production-grade advisory status.
- Missing values must remain missing; do not estimate or silently substitute another source.

## Verification

```bash
backend/.venv/bin/pytest -q
backend/.venv/bin/ruff check backend/app/clients/khoa.py backend/app/clients/kma.py \
  backend/app/clients/resolver.py backend/app/spots.py backend/tests/test_public_api_clients.py
```

## Design Context

Frontend design work is guided by two root docs — read them before UI changes:

- [`PRODUCT.md`](PRODUCT.md) — strategic context. Register `product`, platform `web`. Users: 일반 시민·해양 레저 이용자. Emotional goal: 신뢰·안심 (차분한 명료함). Principles: 코드가 사실의 원천·화면은 인용 / 모르면 '정보없음' 자백 / 침착함이 곧 신뢰 / 비전문가를 위한 쉬운 명료함 / 참고용임을 정직하게. Anti-references: 과장된 대시보드·기술지표판, 공포마케팅·경보 남발, 화려한 그라데이션·글래스모피즘, AI 전면 노출.
- [`design.md`](design.md) — visual system (KRDS 정부 디자인시스템: Government Blue `#256ef4`, 신호등 3색, Pretendard GOV, 플랫+1px 보더, WCAG 2.1 AA). This is the DESIGN.md the impeccable skill reads.

Managed by the project-scoped `impeccable` skill (`.claude/skills/impeccable/`). Run `/impeccable` for design commands (critique, audit, polish, live, …).
