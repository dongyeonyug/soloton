"""환경설정. .env 로드. 인증키는 선택적(없으면 스냅샷/템플릿 폴백)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 기준 프로젝트 루트
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[REPO_ROOT / ".env", BACKEND_DIR / ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    khoa_api_key: str = ""
    khoa_tide_api_key: str = ""
    kma_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # 데이터 provider: auto=키 있으면 hybrid(KHOA 실측+예보 백필), 없으면 openmeteo
    data_provider: Literal["auto", "openmeteo", "khoa", "hybrid"] = "auto"

    use_snapshot_only: bool = True
    force_missing: bool = False

    frontend_origin: str = "http://localhost:5173"

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_live_keys(self) -> bool:
        return bool(self.khoa_api_key and self.kma_api_key)

    @property
    def effective_khoa_tide_api_key(self) -> str:
        """조위 API 키. 별도 키가 없으면 같은 공공데이터포털 KHOA 키를 재사용."""
        return self.khoa_tide_api_key or self.khoa_api_key

    @property
    def resolved_provider(self) -> Literal["openmeteo", "khoa", "hybrid"]:
        """실제 사용할 provider 결정. auto 는 키 있으면 hybrid, 없으면 openmeteo."""
        if self.data_provider == "auto":
            return "hybrid" if self.has_live_keys else "openmeteo"
        return self.data_provider


@lru_cache
def get_settings() -> Settings:
    return Settings()
