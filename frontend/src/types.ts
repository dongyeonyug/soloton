export type Grade = "SAFE" | "CAUTION" | "DANGER";
export type Activity = "조업" | "레저" | "갯바위" | "물놀이";

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
  activity: string;
  spots: SpotOverview[];
}

export interface FilledNumber {
  label: string;
  value: number | null;
  unit: string;
  /** 관측 출처 원문 라벨 (예: "KHOA 해양관측부이(실측)"). 결측이면 빈 문자열. */
  observed_source: string;
  /** "실측" | "예보" | "" — 백엔드 코드가 분류(프론트는 표시만). */
  observed_kind: string;
  /** 판단 기준(임계 밴드). 등급 비반영 참고 지표는 빈 문자열. */
  criterion: string;
  observed_at: string | null;
  is_missing: boolean;
  /** true 면 등급에 반영되지 않는 참고 지표(조위·수온). */
  is_reference: boolean;
}

export interface SafeWindow {
  start: string;
  end: string;
  grade: Grade;
  source: string;
}

export interface Briefing {
  spot_id: string;
  time_slot: string;
  activity: Activity;
  grade: Grade;
  template_text: string;
  llm_prose: string;
  citations: FilledNumber[];
  recommendations: string[];
  is_confession: boolean;
  llm_used: boolean;
  snapshot_as_of: string | null;
  safe_window: SafeWindow | null;
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

export const ACTIVITIES: Activity[] = ["레저", "조업", "갯바위", "물놀이"];
