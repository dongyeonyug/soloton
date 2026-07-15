"""T14: 한 번의 배치 수집에서 공식 API 요청을 관측소 단위로 공유한다."""

import asyncio

from app.clients import khoa, kma, resolver
from app.models import AdvisoryKind, Metric
from app.spots import all_spots, get_spot


def test_khoa_fetches_buoy_and_tide_concurrently(monkeypatch):
    spot = get_spot("haeundae")
    buoy_started = asyncio.Event()
    tide_started = asyncio.Event()
    release = asyncio.Event()

    async def fake_buoy(*args, **kwargs):
        buoy_started.set()
        await release.wait()
        return khoa.KhoaMetrics({Metric.WAVE_HEIGHT: 0.4})

    async def fake_tide(*args, **kwargs):
        tide_started.set()
        await release.wait()
        return khoa.KhoaMetrics({Metric.TIDE_LEVEL: 120.0})

    monkeypatch.setattr(khoa, "fetch_buoy_spot", fake_buoy)
    monkeypatch.setattr(khoa, "fetch_tide_spot", fake_tide)

    async def collect():
        task = asyncio.create_task(khoa.fetch_spot(spot, "buoy-key", "tide-key"))
        await asyncio.wait_for(
            asyncio.gather(buoy_started.wait(), tide_started.wait()), timeout=0.1
        )
        release.set()
        return await task

    result = asyncio.run(collect())
    assert result == {Metric.WAVE_HEIGHT: 0.4, Metric.TIDE_LEVEL: 120.0}


def test_provider_shares_official_requests_for_spots_with_same_stations(monkeypatch):
    calls = {"buoy": 0, "tide": 0, "advisory": 0}

    async def fake_buoy(*args, **kwargs):
        calls["buoy"] += 1
        return khoa.KhoaMetrics({Metric.WAVE_HEIGHT: 0.4})

    async def fake_tide(*args, **kwargs):
        calls["tide"] += 1
        return khoa.KhoaMetrics({Metric.TIDE_LEVEL: 120.0})

    async def fake_scope(*args, **kwargs):
        calls["advisory"] += 1
        return kma.CoastalAdvisoryScope(
            advisory=AdvisoryKind.NONE,
            source_t6="o 폭염주의보 : 부산",
            matched_segments=(),
        )

    monkeypatch.setattr(khoa, "fetch_buoy_spot", fake_buoy)
    monkeypatch.setattr(khoa, "fetch_tide_spot", fake_tide)
    monkeypatch.setattr(kma, "fetch_busan_coastal_scope", fake_scope)
    provider = resolver.KhoaKmaProvider("khoa-key", "kma-key")

    async def collect_two():
        return await asyncio.gather(
            provider.fetch_spot(get_spot("haeundae")),
            provider.fetch_spot(get_spot("gwangalli")),
        )

    readings = asyncio.run(collect_two())
    assert calls == {"buoy": 1, "tide": 1, "advisory": 1}
    assert all(reading is not None for reading in readings)
    assert all(reading.supports_advisory is True for reading in readings)


def test_provider_uses_only_unique_official_sources_across_all_spots(monkeypatch):
    calls = {"buoy": 0, "tide": 0, "advisory": 0}

    async def fake_buoy(*args, **kwargs):
        calls["buoy"] += 1
        return khoa.KhoaMetrics({Metric.WAVE_HEIGHT: 0.4})

    async def fake_tide(*args, **kwargs):
        calls["tide"] += 1
        return khoa.KhoaMetrics({Metric.TIDE_LEVEL: 120.0})

    async def fake_scope(*args, **kwargs):
        calls["advisory"] += 1
        return kma.CoastalAdvisoryScope(AdvisoryKind.NONE, "", ())

    monkeypatch.setattr(khoa, "fetch_buoy_spot", fake_buoy)
    monkeypatch.setattr(khoa, "fetch_tide_spot", fake_tide)
    monkeypatch.setattr(kma, "fetch_busan_coastal_scope", fake_scope)
    provider = resolver.KhoaKmaProvider("khoa-key", "kma-key")

    async def collect_all():
        return await asyncio.gather(*(provider.fetch_spot(spot) for spot in all_spots()))

    asyncio.run(collect_all())
    assert calls == {"buoy": 4, "tide": 2, "advisory": 1}
