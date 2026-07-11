"""DAC2: provider 자동선택 — 키 유무 × 강제설정 조합 검증."""

from app.clients.resolver import get_provider
from app.config import Settings


def _settings(**kw) -> Settings:
    base = dict(khoa_api_key="", kma_api_key="", data_provider="auto")
    base.update(kw)
    return Settings(**base)


def test_auto_no_keys_uses_openmeteo():
    assert get_provider(_settings()).name == "openmeteo"


def test_auto_with_keys_uses_hybrid():
    p = get_provider(_settings(khoa_api_key="k", kma_api_key="m"))
    assert p.name == "hybrid"


def test_force_openmeteo_even_with_keys():
    p = get_provider(_settings(khoa_api_key="k", kma_api_key="m", data_provider="openmeteo"))
    assert p.name == "openmeteo"


def test_force_khoa_pure():
    p = get_provider(_settings(khoa_api_key="k", kma_api_key="m", data_provider="khoa"))
    assert p.name == "khoa"


def test_force_hybrid_without_keys():
    # 강제 hybrid 는 키 없어도 provider 반환(런타임엔 실측 결측→예보 백필)
    p = get_provider(_settings(data_provider="hybrid"))
    assert p.name == "hybrid"


def test_resolved_provider_property():
    assert _settings().resolved_provider == "openmeteo"
    assert _settings(khoa_api_key="k", kma_api_key="m").resolved_provider == "hybrid"
