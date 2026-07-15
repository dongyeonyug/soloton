"""T12/T13: 특보 발표 목록과 부산 연안 적용 근거를 보존하는 원장 검증."""

import asyncio
from datetime import UTC, datetime

from app.clients import kma
from app.models import AdvisoryKind
from app.ingest import advisory_history


RECORD = kma.WarningListRecord(
    stn_id="159",
    tm_fc="202607150030",
    tm_seq=26,
    title="[특보] 제07-26호 : 2026.07.15.00:30 / 풍랑주의보 발표 (*)",
)

SCOPE = kma.CoastalAdvisoryScope(
    advisory=AdvisoryKind.WIND_WAVE_WARNING,
    source_t6="o 풍랑주의보 : 남해동부앞바다, 제주도앞바다",
    matched_segments=(
        kma.CoastalAdvisorySegment(
            advisory=AdvisoryKind.WIND_WAVE_WARNING,
            advisory_name="풍랑주의보",
            regions=("남해동부앞바다", "제주도앞바다"),
            matched_zones=("남해동부앞바다",),
        ),
    ),
)


def test_merge_preserves_existing_records_and_deduplicates():
    captured_at = datetime(2026, 7, 16, 1, tzinfo=UTC)
    first, changed = advisory_history.merge_advisory_history(
        advisory_history._empty_history(), [RECORD], captured_at=captured_at
    )
    second, changed_again = advisory_history.merge_advisory_history(
        first, [RECORD], captured_at=datetime(2026, 7, 16, 7, tzinfo=UTC)
    )

    assert changed is True
    assert changed_again is False
    assert second["records"] == first["records"]
    assert second["records"][0]["captured_at"] == "2026-07-16T01:00:00+00:00"


def test_merge_appends_scope_only_when_busan_coastal_result_changes():
    first, changed = advisory_history.merge_advisory_history(
        advisory_history._empty_history(), [], captured_at=datetime(2026, 7, 16, tzinfo=UTC), scope=SCOPE
    )
    second, unchanged = advisory_history.merge_advisory_history(
        first, [], captured_at=datetime(2026, 7, 16, 6, tzinfo=UTC), scope=SCOPE
    )
    no_advisory = kma.CoastalAdvisoryScope(
        advisory=AdvisoryKind.NONE,
        source_t6="o 폭염주의보 : 부산",
        matched_segments=(),
    )
    third, changed_again = advisory_history.merge_advisory_history(
        second, [], captured_at=datetime(2026, 7, 16, 12, tzinfo=UTC), scope=no_advisory
    )

    assert changed is True
    assert unchanged is False
    assert changed_again is True
    assert len(third["scope_captures"]) == 2
    assert third["scope_captures"][0]["source_t6"] == SCOPE.source_t6
    assert third["scope_captures"][1]["selected_advisory"] == "none"


def test_capture_stores_recent_records_without_rewriting_duplicates(monkeypatch, tmp_path):
    calls = []

    async def fake_fetch(api_key, *, from_date, to_date, station_id):
        calls.append((api_key, from_date, to_date, station_id))
        return [RECORD]

    monkeypatch.setattr(advisory_history.kma, "fetch_warning_list", fake_fetch)
    monkeypatch.setattr(advisory_history.kma, "fetch_busan_coastal_scope", lambda _key: _scope())
    path = tmp_path / "advisory_history.json"
    now = datetime(2026, 7, 16, 0, tzinfo=UTC)

    first = asyncio.run(advisory_history.capture_advisory_history("key", now=now, path=path))
    before = path.read_text(encoding="utf-8")
    second = asyncio.run(advisory_history.capture_advisory_history("key", now=now, path=path))

    assert first == advisory_history.AdvisoryHistoryCapture(1, 1, True)
    assert second == advisory_history.AdvisoryHistoryCapture(1, 1, False)
    assert path.read_text(encoding="utf-8") == before
    assert calls[0] == ("key", calls[0][1], calls[0][2], "159")
    assert calls[0][1].isoformat() == "2026-07-10"
    assert calls[0][2].isoformat() == "2026-07-16"


def test_capture_interprets_snapshot_timestamps_as_utc(monkeypatch, tmp_path):
    calls = []

    async def fake_fetch(api_key, *, from_date, to_date, station_id):
        calls.append((from_date, to_date))
        return []

    monkeypatch.setattr(advisory_history.kma, "fetch_warning_list", fake_fetch)
    monkeypatch.setattr(advisory_history.kma, "fetch_busan_coastal_scope", lambda _key: _scope())
    # SnapshotDoc이 저장하는 UTC naive 시각. KST로 바꾸면 다음 날이어야 한다.
    now = datetime(2026, 7, 15, 16, 6, 30)

    result = asyncio.run(
        advisory_history.capture_advisory_history("key", now=now, path=tmp_path / "history.json")
    )

    assert result == advisory_history.AdvisoryHistoryCapture(0, 1, True)
    assert len(calls) == 1
    assert calls[0][0].isoformat() == "2026-07-10"
    assert calls[0][1].isoformat() == "2026-07-16"


def test_capture_failure_preserves_existing_history(monkeypatch, tmp_path):
    path = tmp_path / "advisory_history.json"
    original, _ = advisory_history.merge_advisory_history(
        advisory_history._empty_history(), [RECORD], captured_at=datetime(2026, 7, 16, tzinfo=UTC)
    )
    advisory_history.write_advisory_history(original, path)
    before = path.read_text(encoding="utf-8")

    async def fail(*args, **kwargs):
        raise RuntimeError("KMA unavailable")

    monkeypatch.setattr(advisory_history.kma, "fetch_warning_list", fail)
    monkeypatch.setattr(advisory_history.kma, "fetch_busan_coastal_scope", fail)
    result = asyncio.run(advisory_history.capture_advisory_history("key", path=path))

    assert result is None
    assert path.read_text(encoding="utf-8") == before


def test_capture_does_not_overwrite_a_corrupt_history(monkeypatch, tmp_path):
    path = tmp_path / "advisory_history.json"
    path.write_text("{not json", encoding="utf-8")

    async def fake_fetch(*args, **kwargs):
        return [RECORD]

    monkeypatch.setattr(advisory_history.kma, "fetch_warning_list", fake_fetch)
    result = asyncio.run(advisory_history.capture_advisory_history("key", path=path))

    assert result is None
    assert path.read_text(encoding="utf-8") == "{not json"


def test_capture_preserves_scope_when_warning_list_is_unavailable(monkeypatch, tmp_path):
    async def fail(*args, **kwargs):
        raise RuntimeError("warning list unavailable")

    monkeypatch.setattr(advisory_history.kma, "fetch_warning_list", fail)
    monkeypatch.setattr(advisory_history.kma, "fetch_busan_coastal_scope", lambda _key: _scope())

    result = asyncio.run(
        advisory_history.capture_advisory_history("key", path=tmp_path / "history.json")
    )

    assert result == advisory_history.AdvisoryHistoryCapture(None, 1, True)


async def _scope() -> kma.CoastalAdvisoryScope:
    return SCOPE
