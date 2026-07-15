"""기상청 특보 목록의 짧은 API 보존 기간을 보완하는 append-only 원장."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ..clients import kma
from ..config import DATA_DIR

ADVISORY_HISTORY_PATH = DATA_DIR / "advisory_history.json"
ADVISORY_HISTORY_SCHEMA_VERSION = 2
KMA_ARCHIVE_STATION_ID = "159"
KMA_WINDOW_DAYS = 6
KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class AdvisoryHistoryCapture:
    """한 번의 원장 수집 결과. ``None`` 개수는 해당 API 조회 실패를 뜻한다."""

    warning_record_count: int | None
    scope_capture_count: int | None
    changed: bool


def _empty_history() -> dict[str, Any]:
    return {
        "schema_version": ADVISORY_HISTORY_SCHEMA_VERSION,
        "source": {
            "provider": "기상청 기상특보 조회서비스",
            "data_id": "15000415",
            "operation": "getWthrWrnList",
            "source_url": "https://www.data.go.kr/data/15000415/openapi.do",
            "station_id": KMA_ARCHIVE_STATION_ID,
            "window_days": KMA_WINDOW_DAYS,
            "scope_note": (
                "특보 목록은 공식 발표 기록이다. 개별 부산 연안 지점의 발효 해역 여부는 "
                "scope_captures의 현재 특보 t6 구조 파서 기록으로 별도 확인하며, 이 원장만으로 "
                "판단하지 않는다."
            ),
            "scope_capture": {
                "operation": "getPwnStatus",
                "endpoint": kma.KMA_URL,
                "matched_zones": list(kma.BUSAN_SEA_ZONES),
                "capture_policy": "부산 연안 귀속 결과가 바뀔 때만 append-only로 보존",
                "limit_note": "관측된 시점의 상태 전환 기록이며 특보의 연속 발효 기간 증명은 아니다.",
            },
        },
        "records": [],
        "scope_captures": [],
    }


def load_advisory_history(path: Path = ADVISORY_HISTORY_PATH) -> dict[str, Any] | None:
    """원장이 없으면 빈 원장, 손상됐으면 ``None``을 반환해 덮어쓰기를 막는다."""
    if not path.exists():
        return _empty_history()
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        return None
    if "scope_captures" in payload and not isinstance(payload["scope_captures"], list):
        return None
    return payload


def merge_advisory_history(
    history: dict[str, Any],
    records: list[kma.WarningListRecord],
    *,
    captured_at: datetime,
    scope: kma.CoastalAdvisoryScope | None = None,
) -> tuple[dict[str, Any], bool]:
    """새 공식 발표·해역 귀속 상태만 추가한다. 기존 기록 시각은 바꾸지 않는다."""
    merged = _empty_history()
    existing_records = history.get("records", [])
    by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    for record in existing_records:
        if not isinstance(record, dict):
            continue
        try:
            key = (str(record["stn_id"]), str(record["tm_fc"]), int(record["tm_seq"]))
        except (KeyError, TypeError, ValueError):
            continue
        by_key[key] = record

    changed = False
    for record in records:
        if record.key in by_key:
            continue
        by_key[record.key] = {
            "stn_id": record.stn_id,
            "tm_fc": record.tm_fc,
            "tm_seq": record.tm_seq,
            "title": record.title,
            "captured_at": captured_at.isoformat(),
        }
        changed = True

    merged["records"] = sorted(
        by_key.values(),
        key=lambda record: (str(record["tm_fc"]), int(record["tm_seq"])),
    )
    existing_scopes = history.get("scope_captures", [])
    if not isinstance(existing_scopes, list):
        raise ValueError("scope_captures must be a list")
    merged["scope_captures"] = list(existing_scopes)
    if scope is not None:
        capture = _scope_capture(scope, captured_at)
        previous = merged["scope_captures"][-1] if merged["scope_captures"] else None
        if _scope_fingerprint(previous) != _scope_fingerprint(capture):
            merged["scope_captures"].append(capture)
            changed = True
    return merged, changed


def _scope_capture(
    scope: kma.CoastalAdvisoryScope,
    captured_at: datetime,
) -> dict[str, Any]:
    return {
        "captured_at": captured_at.isoformat(),
        "selected_advisory": scope.advisory.value,
        "matched_segments": [segment.as_history_dict() for segment in scope.matched_segments],
        "source_t6": scope.source_t6,
    }


def _scope_fingerprint(capture: Any) -> str | None:
    """원문 내 무관한 육상 특보 변화는 이력 전환으로 기록하지 않는다."""
    if not isinstance(capture, dict):
        return None
    advisory = capture.get("selected_advisory")
    segments = capture.get("matched_segments")
    if not isinstance(advisory, str) or not isinstance(segments, list):
        return None
    return json.dumps(
        {"selected_advisory": advisory, "matched_segments": segments},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def write_advisory_history(history: dict[str, Any], path: Path = ADVISORY_HISTORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


async def capture_advisory_history(
    api_key: str,
    *,
    now: datetime | None = None,
    path: Path = ADVISORY_HISTORY_PATH,
) -> AdvisoryHistoryCapture | None:
    """최근 공식 특보 목록을 누적한다.

    ``None``은 키 부재, 원장 파싱 실패 또는 두 API의 조회 실패를 의미한다. 이 경우
    기존 원장은 보존한다.
    발표 목록과 현재 해역 귀속을 독립적으로 조회한다. 한쪽만 실패해도 다른 쪽의
    새 기록은 보존하며, 둘 다 실패했을 때만 ``None``을 반환한다.
    """
    if not api_key:
        return None
    # SnapshotDoc의 as_of는 UTC naive로 저장된다. naive 값을 시스템 로컬 시각으로
    # 해석하면 조회 날짜가 밀려 API 보존 범위를 벗어날 수 있으므로 UTC를 명시한다.
    captured_at = now or datetime.now(UTC)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=UTC)
    captured_at = captured_at.astimezone(KST)
    history = load_advisory_history(path)
    if history is None:
        return None
    warning_result, scope_result = await asyncio.gather(
        _fetch_warning_records(
            api_key,
            from_date=captured_at.date() - timedelta(days=KMA_WINDOW_DAYS),
            to_date=captured_at.date(),
        ),
        _fetch_coastal_scope(api_key),
    )
    records = warning_result if isinstance(warning_result, list) else None
    scope = scope_result if isinstance(scope_result, kma.CoastalAdvisoryScope) else None
    if records is None and scope is None:
        return None
    merged, changed = merge_advisory_history(
        history,
        records or [],
        captured_at=captured_at,
        scope=scope,
    )
    if changed:
        try:
            write_advisory_history(merged, path)
        except OSError:
            return None
    return AdvisoryHistoryCapture(
        warning_record_count=len(records) if records is not None else None,
        scope_capture_count=len(merged["scope_captures"]) if scope is not None else None,
        changed=changed,
    )


async def _fetch_warning_records(
    api_key: str,
    *,
    from_date: date,
    to_date: date,
) -> list[kma.WarningListRecord] | None:
    try:
        return await kma.fetch_warning_list(
            api_key,
            from_date=from_date,
            to_date=to_date,
            station_id=KMA_ARCHIVE_STATION_ID,
        )
    except Exception:
        return None

async def _fetch_coastal_scope(api_key: str) -> kma.CoastalAdvisoryScope | None:
    try:
        return await kma.fetch_busan_coastal_scope(api_key)
    except Exception:
        return None


def main() -> None:
    """원장만 수동 갱신할 때 쓰는 진입점."""
    from ..config import get_settings

    result = asyncio.run(capture_advisory_history(get_settings().kma_api_key))
    if result is None:
        print("advisory history skipped: KMA key missing or list API unavailable")
        return
    print(
        "advisory history captured: "
        f"source_records={result.warning_record_count}, "
        f"scope_captures={result.scope_capture_count}, changed={result.changed}"
    )


if __name__ == "__main__":
    main()
