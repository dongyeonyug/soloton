"""테스트 공용 헬퍼 — 골드 케이스 dict → 엔진 입력."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.models import (
    Activity,
    Advisory,
    AdvisoryKind,
    MarineObservation,
    Metric,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FIXED_TIME = datetime(2026, 7, 10, 9, 0, 0)


def load_gold_cases() -> list[dict]:
    with open(DATA_DIR / "gold_cases.json", encoding="utf-8") as f:
        return json.load(f)["cases"]


def _obs(spot_id: str, metric: Metric, value: float | None, unit: str, source: str) -> MarineObservation:
    return MarineObservation(
        spot_id=spot_id,
        metric=metric,
        value=value,
        unit=unit,
        observed_at=None if value is None else FIXED_TIME,
        source=source,
        is_missing=value is None,
    )


def build_inputs(case: dict, spot_id: str = "test"):
    """골드 케이스 → (observations, advisory, activity)."""
    observations = {
        Metric.WAVE_HEIGHT: _obs(spot_id, Metric.WAVE_HEIGHT, case.get("wave"), "m", "KHOA"),
        Metric.WIND_SPEED: _obs(spot_id, Metric.WIND_SPEED, case.get("wind"), "m/s", "KMA"),
        Metric.CURRENT_SPEED: _obs(spot_id, Metric.CURRENT_SPEED, case.get("current"), "m/s", "KHOA"),
    }
    kind = AdvisoryKind(case.get("advisory", "none"))
    advisory = Advisory(
        kind=kind,
        effective_at=None if kind is AdvisoryKind.NONE else FIXED_TIME,
        source="KMA",
    )
    activity = Activity(case["activity"])
    return observations, advisory, activity
