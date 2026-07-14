"""도메인 데이터 모델.

핵심 불변식: 브리핑의 모든 수치·등급은 코드가 소유한다. `basis_values` 는 등급이
어떤 관측값에서 파생됐는지 라벨과 함께 추적하며, 슬롯필 계층은 이 라벨된 값에만
바인딩한다(AC4 attribution). LLM 은 여기의 어떤 숫자도 생성하지 않는다.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Grade(str, Enum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    DANGER = "DANGER"

    @property
    def rank(self) -> int:
        return {"SAFE": 0, "CAUTION": 1, "DANGER": 2}[self.value]

    @property
    def label_ko(self) -> str:
        return {"SAFE": "안전", "CAUTION": "주의", "DANGER": "위험"}[self.value]


class Metric(str, Enum):
    WAVE_HEIGHT = "wave_height"      # 유의파고 (m)
    WIND_SPEED = "wind_speed"        # 해상 풍속 (m/s)
    CURRENT_SPEED = "current_speed"  # 조류 유속 (m/s)
    TIDE_LEVEL = "tide_level"        # 조위 (cm) — 참고 지표(등급 비임계)
    WATER_TEMP = "water_temp"        # 수온 (°C) — 참고 지표


# 등급을 좌우하는 임계 지표. 이 중 하나라도 결측이면 안전 불가(CAUTION floor).
CRITICAL_METRICS: frozenset[Metric] = frozenset(
    {Metric.WAVE_HEIGHT, Metric.WIND_SPEED}
)


class AdvisoryKind(str, Enum):
    NONE = "none"
    WIND_WAVE_WARNING = "풍랑주의보"
    WIND_WAVE_ALERT = "풍랑경보"
    WAVE_WARNING = "풍파주의보"
    WAVE_ALERT = "풍파경보"


class Activity(str, Enum):
    FISHING = "조업"        # 소형선박
    LEISURE = "레저"        # 요트/보트
    ROCK_FISHING = "갯바위"  # 갯바위 낚시
    SWIMMING = "물놀이"      # 해수욕/입수


class SpotType(str, Enum):
    PORT = "항"
    BEACH = "해수욕장"
    ROCK = "갯바위"


class Spot(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    type: SpotType
    khoa_obs_code: str | None = None
    khoa_tide_obs_code: str | None = None
    kma_area: str | None = None


class MarineObservation(BaseModel):
    """지표 1개당 1행. 개별 관측 시각·결측 플래그를 가진다(AC1)."""

    spot_id: str
    metric: Metric
    value: float | None = None
    unit: str
    observed_at: datetime | None = None
    source: str
    is_missing: bool = False
    fetched_at: datetime | None = None


class Advisory(BaseModel):
    kind: AdvisoryKind
    threshold_value: float | None = None
    effective_at: datetime | None = None
    source: str
    is_missing: bool = False


class BasisValue(BaseModel):
    """등급 파생의 근거. 라벨-수치 오결합(AC4)을 막는 attribution 단위.

    observed_source(값이 어디서 왔나: KHOA 실측 / Open-Meteo 예보)와
    criterion(등급을 가른 판단 기준: 임계 밴드)은 서로 다른 사실이므로 분리 보관한다.
    """

    label: str          # 예: "유의파고"
    metric: Metric
    value: float | None  # 결측이면 None
    unit: str
    observed_source: str = ""   # 관측 출처 — MarineObservation.source 를 그대로 전달
    criterion: str = ""         # 판단 기준 — 임계 밴드 텍스트(구 source, 의미 교정 개명)
    observed_at: datetime | None = None
    is_missing: bool = False
    is_reference: bool = False  # True 면 등급 비반영 참고 지표(조위·수온)
    contributed_grade: Grade


class RiskGrade(BaseModel):
    grade: Grade
    time_slot: str
    activity: Activity
    basis_values: list[BasisValue] = Field(default_factory=list)
    basis_advisories: list[Advisory] = Field(default_factory=list)
    has_missing_critical: bool = False


class FilledNumber(BaseModel):
    """슬롯필 수치 슬롯. 코드만 채운다. label 은 반드시 자신의 metric 에서 유래."""

    label: str
    value: float | None
    unit: str
    observed_source: str = ""   # 관측 출처(실측/예보 원문 라벨)
    observed_kind: str = ""     # "실측" | "예보" | "" — UI 배지용, 코드가 분류
    criterion: str = ""         # 판단 기준(임계 밴드) — 등급 비반영 참고 지표는 빈 문자열
    observed_at: datetime | None = None
    is_missing: bool = False
    is_reference: bool = False


class BriefingSlots(BaseModel):
    spot_id: str
    time_slot: str
    activity: Activity
    grade: Grade
    filled_numbers: list[FilledNumber] = Field(default_factory=list)
    is_confession: bool = False
    snapshot_as_of: datetime | None = None


class Briefing(BaseModel):
    spot_id: str
    time_slot: str
    activity: Activity
    grade: Grade
    template_text: str
    llm_prose: str
    citations: list[FilledNumber] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    is_confession: bool = False
    llm_used: bool = False           # False 면 가드/폴백으로 템플릿만 서빙
    snapshot_as_of: datetime | None = None
    # E2: 엔진이 고른 '가장 안전한 시간대'(예보 기반). 데이터 없으면 None.
    safe_window: "SafeWindow | None" = None


class ForecastPoint(BaseModel):
    """시간별 예보값(코드 소유 수치). '가장 안전한 시간' 계산의 입력.

    예보는 본질적으로 Open-Meteo(수치예보) 소스이며 실측이 아니다. 값은 결측 가능하고,
    결측이면 해당 시각은 등급 산정에서 제외한다(추정 금지).
    """

    time: datetime
    wave_height: float | None = None
    wind_speed: float | None = None


class SafeWindow(BaseModel):
    """엔진이 결정론적으로 고른 '가장 안전한 시간대'. 시각은 코드가 소유(인용 슬롯).

    grade 는 그 시간대의 확정 등급 — SAFE 창이 없으면 가장 나은(덜 위험한) 창을 고르되
    등급을 정직하게 표기한다. LLM 은 이 시각을 생성하지 않고 산문에서 숫자 없이 참조만.
    """

    start: datetime
    end: datetime
    grade: Grade
    source: str = "Open-Meteo 예보(수치모델)"


# Briefing 이 뒤에 정의된 SafeWindow 를 전방참조하므로 여기서 확정한다.
Briefing.model_rebuild()
