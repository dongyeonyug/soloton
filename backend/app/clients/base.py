"""HTTP 기반 클래스 + provider 계약. 실패는 None 으로 흡수(호출측이 결측 처리)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

import httpx

from ..models import AdvisoryKind, Metric, MissingReason
from ..spots import Spot

DEFAULT_TIMEOUT = 10.0
MAX_RETRIES = 3
BACKOFF_BASE = 0.5


@dataclass
class ProviderReading:
    """provider-중립 관측 결과. present 값만 담고, 없는 지표는 아예 넣지 않는다.

    supports_advisory=False 는 "이 provider 는 기상특보를 제공하지 않음"을 뜻하며,
    이 경우 normalize 는 특보를 '없음(NONE, 결측 아님)'으로 처리해 SAFE 등급을
    붕괴시키지 않는다(등급 결측-플로어는 파고/풍속에만 적용).
    """

    metrics: dict[Metric, float] = field(default_factory=dict)
    advisory: AdvisoryKind = AdvisoryKind.NONE
    supports_advisory: bool = False
    advisory_is_missing: bool = False
    observed_at: datetime | None = None
    # 서로 다른 소스가 섞인 경우 각 수치의 실제 관측 시각을 보존한다.
    metric_observed_at: dict[Metric, datetime] = field(default_factory=dict)
    # 지표별 출처 라벨(하이브리드 실측/예보 구분). 없으면 provider.source_labels 사용.
    metric_sources: dict[Metric, str] = field(default_factory=dict)
    # 지표가 없을 때의 수집 원인. 값이 있는 지표에는 절대 넣지 않는다.
    metric_missing_reasons: dict[Metric, MissingReason] = field(default_factory=dict)


@runtime_checkable
class MarineProvider(Protocol):
    name: str
    source_labels: dict[Metric, str]

    async def fetch_spot(self, spot: Spot) -> ProviderReading | None:
        """지점 관측 조회. 실패 시 None(전량 결측)."""
        ...


async def fetch_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
) -> Any | None:
    """GET → JSON. 모든 재시도 실패 시 None(크래시 없음)."""
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError):  # ValueError = JSON decode
            if attempt < retries - 1:
                await asyncio.sleep(BACKOFF_BASE * (2**attempt))
    # 모든 재시도 소진 → 결측 신호
    return None
