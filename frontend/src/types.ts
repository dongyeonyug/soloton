export type Grade = "SAFE" | "CAUTION" | "DANGER";
export type ProseStatus =
  | "verified"
  | "blocked_by_guard"
  | "generation_unavailable"
  | "deterministic_fallback";
export type DataStatus = "observed" | "forecast" | "available" | "missing" | "stale";
export type MissingReason =
  | "source_not_supported"
  | "no_station_mapping"
  | "source_returned_no_value"
  | "source_unavailable"
  | "source_timeout"
  | "legacy_unknown";
export type RuleEvidence = "official_baseline" | "conservative_mapping";
export type SafeWindowStatus =
  | "available"
  | "forecast_unavailable"
  | "no_future_forecast"
  | "incomplete_forecast"
  | "no_safe_window";
export type PlanActivity = "water_play";
export type PlanDataState = "ready" | "partial" | "stale" | "unavailable" | "invalid_time";
export type PlanCoverageState =
  | "detailed"
  | "partial"
  | "stale"
  | "unavailable"
  | "invalid_time";

export interface SpotOverview {
  id: string;
  name: string;
  lat: number;
  lng: number;
  type: string;
  grade: Grade;
  grade_ko: string;
  has_missing_critical: boolean;
}

export interface Overview {
  snapshot_as_of: string;
  spots: SpotOverview[];
}

export interface FilledNumber {
  label: string;
  value: number | null;
  unit: string;
  /** 관측 출처 원문 라벨 (예: "KHOA 해양관측부이(실측)"). 결측이면 빈 문자열. */
  observed_source: string;
  /** 결측이어도 값을 확인하려고 조회한 출처. */
  checked_source: string;
  /** "실측" | "예보" | "" — 백엔드 코드가 분류(프론트는 표시만). */
  observed_kind: string;
  /** 판단 기준(임계 밴드). 등급 비반영 참고 지표는 빈 문자열. */
  criterion: string;
  rule_evidence: RuleEvidence | null;
  observed_at: string | null;
  is_missing: boolean;
  missing_reason: MissingReason | null;
  data_status: DataStatus;
  /** 파고·풍속처럼 결측이면 안전 등급을 막는 핵심 입력인지 여부. */
  is_critical: boolean;
  /** true 면 등급에 반영되지 않는 참고 지표(조위·수온). */
  is_reference: boolean;
  /** 등급 비반영 사유 또는 참고 범위. */
  reference_note: string;
  reference_station_name: string | null;
  reference_station_code: string | null;
  reference_distance_km: number | null;
}

export interface Advisory {
  kind: string;
  effective_at: string | null;
  source: string;
  is_missing: boolean;
  is_stale: boolean;
}

export interface SafeWindow {
  start: string;
  end: string;
  grade: Grade;
  source: string;
  horizon_hours: number;
  forecast_points_considered: number;
  forecast_points_graded: number;
  selected_points: number;
  selection_rule: string;
}

export interface SafeWindowAssessment {
  status: SafeWindowStatus;
  detail: string;
  source: string;
  forecast_collected_at: string | null;
  horizon_hours: number;
  forecast_points_collected: number;
  forecast_points_considered: number;
  forecast_points_graded: number;
  selection_rule: string;
  safe_window: SafeWindow | null;
}

export interface DecisionStep {
  label: string;
  detail: string;
  result_grade: Grade | null;
  rule_evidence: RuleEvidence | null;
}

export interface Briefing {
  spot_id: string;
  time_slot: string;
  grade: Grade;
  template_text: string;
  llm_prose: string;
  citations: FilledNumber[];
  recommendations: string[];
  is_confession: boolean;
  has_missing_critical: boolean;
  advisory: Advisory | null;
  decision_steps: DecisionStep[];
  prose_status: ProseStatus;
  snapshot_as_of: string | null;
  safe_window: SafeWindow | null;
  safe_window_assessment: SafeWindowAssessment | null;
}

export interface PlanOptions {
  spot_id: string;
  activity: PlanActivity;
  forecast_times: string[];
  forecast_status: string;
  forecast_collected_at: string | null;
  snapshot_as_of: string;
}

export interface ForecastConditions {
  forecast_at: string;
  grade: Grade | null;
  citations: FilledNumber[];
  has_missing_critical: boolean;
  source: string;
}

export interface CurrentAdvisory {
  advisory: Advisory;
  checked_at: string | null;
  scope_label: string;
}

export interface OfficialLink {
  label: string;
  url: string;
  source_owner: string;
  activity_scope: PlanActivity;
  region_scope: string;
  last_verified_at: string;
  fallback_text: string;
}

export interface PlanBriefing {
  spot_id: string;
  activity: PlanActivity;
  requested_at: string;
  data_state: PlanDataState;
  coverage_state: PlanCoverageState;
  forecast_conditions: ForecastConditions | null;
  current_advisory: CurrentAdvisory | null;
  action: string;
  limitations: string[];
  official_links: OfficialLink[];
  snapshot_as_of: string | null;
}

export interface PlanIntent {
  spot_id: string;
  activity: PlanActivity;
  requested_at: string;
}

/** E1 — 가드 판정 결과. 위반 스팬은 코드포인트 오프셋(백엔드 guard 와 동일 규칙). */
export interface GuardVerdict {
  text: string;
  violations: string[];
  violation_spans: [number, number][];
  blocked: boolean;
  served_prose: string;
  llm_used: boolean;
}

export interface GuardCase extends GuardVerdict {
  id: string;
  title: string;
  note: string;
}

export interface GuardDemo {
  spot_id: string;
  spot_name: string;
  grade: Grade;
  cases: GuardCase[];
}

export const GRADE_COLOR: Record<Grade, string> = {
  SAFE: "#228738",
  CAUTION: "#9e6a00",
  DANGER: "#de3412",
};

export const GRADE_KO: Record<Grade, string> = {
  SAFE: "안전",
  CAUTION: "주의",
  DANGER: "위험",
};
