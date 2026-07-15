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


class ProseStatus(str, Enum):
    """브리핑 산문의 생성·검증 결과.

    공개 요청은 이 상태를 새로 생성하지 않는다. 배치에서 저장한 결과를 다시 가드로
    확인하거나, 코드 폴백을 선택한 이유만 응답에 드러낸다.
    """

    VERIFIED = "verified"
    BLOCKED_BY_GUARD = "blocked_by_guard"
    GENERATION_UNAVAILABLE = "generation_unavailable"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"


class DataStatus(str, Enum):
    """지표 값의 이용 가능 상태. 표시는 프런트가 맡고 판정은 코드가 맡는다."""

    OBSERVED = "observed"
    FORECAST = "forecast"
    AVAILABLE = "available"
    MISSING = "missing"
    STALE = "stale"


class MissingReason(str, Enum):
    """결측의 수집 단계 원인. 값 자체의 출처와 혼동하지 않는다."""

    SOURCE_NOT_SUPPORTED = "source_not_supported"
    NO_STATION_MAPPING = "no_station_mapping"
    SOURCE_RETURNED_NO_VALUE = "source_returned_no_value"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_TIMEOUT = "source_timeout"
    LEGACY_UNKNOWN = "legacy_unknown"


class RuleEvidence(str, Enum):
    """임계값이 어디까지 검증된 기준인지 나타낸다."""

    OFFICIAL_BASELINE = "official_baseline"
    CONSERVATIVE_MAPPING = "conservative_mapping"


class ForecastCollectionStatus(str, Enum):
    """시간별 예보 수집 결과. 위험도 입력 결측과 별도로 보존한다."""

    AVAILABLE = "available"
    EMPTY_RESPONSE = "empty_response"
    SOURCE_TIMEOUT = "source_timeout"
    SOURCE_UNAVAILABLE = "source_unavailable"
    LEGACY_UNKNOWN = "legacy_unknown"


class SafeWindowStatus(str, Enum):
    """시간대 계산 결과. 시간대를 만들지 않은 이유도 코드가 소유한다."""

    AVAILABLE = "available"
    FORECAST_UNAVAILABLE = "forecast_unavailable"
    NO_FUTURE_FORECAST = "no_future_forecast"
    INCOMPLETE_FORECAST = "incomplete_forecast"
    NO_SAFE_WINDOW = "no_safe_window"


class Metric(str, Enum):
    WAVE_HEIGHT = "wave_height"      # 유의파고 (m)
    WIND_SPEED = "wind_speed"        # 해상 풍속 (m/s)
    CURRENT_SPEED = "current_speed"  # 조류 유속 (m/s) — 지역 임계값 검증 전 참고값
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
    is_stale: bool = False
    missing_reason: MissingReason | None = None
    fetched_at: datetime | None = None
    # 조위처럼 서비스 지점이 아닌 관측소 값을 참고하는 경우의 위치적 한계.
    reference_station_name: str | None = None
    reference_station_code: str | None = None
    reference_distance_km: float | None = None


class Advisory(BaseModel):
    kind: AdvisoryKind
    threshold_value: float | None = None
    effective_at: datetime | None = None
    source: str
    is_missing: bool = False
    is_stale: bool = False


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
    checked_source: str = ""    # 결측이어도 확인을 시도한 출처. 관측값 출처와 구분한다.
    criterion: str = ""         # 판단 기준 — 임계 밴드 텍스트(구 source, 의미 교정 개명)
    rule_evidence: RuleEvidence | None = None
    observed_at: datetime | None = None
    is_missing: bool = False
    missing_reason: MissingReason | None = None
    data_status: DataStatus = DataStatus.MISSING
    is_critical: bool = False
    is_reference: bool = False  # True 면 등급 비반영 참고 지표
    reference_note: str = ""    # 등급 비반영 사유 또는 참고 범위
    reference_station_name: str | None = None
    reference_station_code: str | None = None
    reference_distance_km: float | None = None
    contributed_grade: Grade


class RiskGrade(BaseModel):
    grade: Grade
    time_slot: str
    basis_values: list[BasisValue] = Field(default_factory=list)
    basis_advisories: list[Advisory] = Field(default_factory=list)
    advisory: Advisory | None = None
    decision_steps: list["DecisionStep"] = Field(default_factory=list)
    has_missing_critical: bool = False


class FilledNumber(BaseModel):
    """슬롯필 수치 슬롯. 코드만 채운다. label 은 반드시 자신의 metric 에서 유래."""

    label: str
    value: float | None
    unit: str
    observed_source: str = ""   # 관측 출처(실측/예보 원문 라벨)
    checked_source: str = ""    # 결측일 때도 확인을 시도한 데이터 출처
    observed_kind: str = ""     # "실측" | "예보" | "" — UI 배지용, 코드가 분류
    criterion: str = ""         # 판단 기준(임계 밴드) — 등급 비반영 참고 지표는 빈 문자열
    rule_evidence: RuleEvidence | None = None
    observed_at: datetime | None = None
    is_missing: bool = False
    missing_reason: MissingReason | None = None
    data_status: DataStatus = DataStatus.MISSING
    is_critical: bool = False
    is_reference: bool = False
    reference_note: str = ""
    reference_station_name: str | None = None
    reference_station_code: str | None = None
    reference_distance_km: float | None = None


class BriefingSlots(BaseModel):
    spot_id: str
    time_slot: str
    grade: Grade
    filled_numbers: list[FilledNumber] = Field(default_factory=list)
    is_confession: bool = False
    snapshot_as_of: datetime | None = None


class Briefing(BaseModel):
    spot_id: str
    time_slot: str
    grade: Grade
    template_text: str
    llm_prose: str
    citations: list[FilledNumber] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    is_confession: bool = False
    has_missing_critical: bool = False
    advisory: Advisory | None = None
    decision_steps: list["DecisionStep"] = Field(default_factory=list)
    prose_status: ProseStatus = ProseStatus.DETERMINISTIC_FALLBACK
    snapshot_as_of: datetime | None = None
    # E2: 엔진이 고른 '가장 안전한 시간대'(예보 기반). 데이터 없으면 None.
    safe_window: "SafeWindow | None" = None
    safe_window_assessment: "SafeWindowAssessment | None" = None


class ForecastPoint(BaseModel):
    """시간별 예보값(코드 소유 수치). '가장 안전한 시간' 계산의 입력.

    예보는 본질적으로 Open-Meteo(수치예보) 소스이며 실측이 아니다. 값은 결측 가능하고,
    결측이면 해당 시각은 등급 산정에서 제외한다(추정 금지).
    """

    time: datetime
    wave_height: float | None = None
    wind_speed: float | None = None


class DecisionStep(BaseModel):
    """코드가 기록한 위험도 결정 과정의 한 단계."""

    label: str
    detail: str
    result_grade: Grade | None = None
    rule_evidence: RuleEvidence | None = None


class SafeWindow(BaseModel):
    """엔진이 결정론적으로 고른 '가장 안전한 시간대'. 시각은 코드가 소유(인용 슬롯).

    grade 는 그 시간대의 확정 등급 — SAFE 창이 없으면 가장 나은(덜 위험한) 창을 고르되
    등급을 정직하게 표기한다. LLM 은 이 시각을 생성하지 않고 산문에서 숫자 없이 참조만.
    """

    start: datetime
    end: datetime
    grade: Grade
    source: str = "Open-Meteo 예보(수치모델)"
    horizon_hours: int = 12
    forecast_points_considered: int = 0
    forecast_points_graded: int = 0
    selected_points: int = 0
    selection_rule: str = "안전 시각을 우선하고, 없으면 주의 시각 중 가장 이른 연속 구간을 선택"


class SafeWindowAssessment(BaseModel):
    """시간대 선택 또는 계산 불가 사유를 포함한 코드 소유 평가 결과."""

    status: SafeWindowStatus
    detail: str
    source: str = "Open-Meteo 예보(수치모델)"
    forecast_collected_at: datetime | None = None
    horizon_hours: int = 12
    forecast_points_collected: int = 0
    forecast_points_considered: int = 0
    forecast_points_graded: int = 0
    selection_rule: str = "안전 시각을 우선하고, 없으면 주의 시각 중 가장 이른 연속 구간을 선택"
    safe_window: SafeWindow | None = None


# Briefing 이 뒤에 정의된 SafeWindow 를 전방참조하므로 여기서 확정한다.
Briefing.model_rebuild()
RiskGrade.model_rebuild()
