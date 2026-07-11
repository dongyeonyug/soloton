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
  source: string;
  observed_at: string | null;
  is_missing: boolean;
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
}

export const GRADE_COLOR: Record<Grade, string> = {
  SAFE: "#1e9e5a",
  CAUTION: "#e8a33d",
  DANGER: "#d64545",
};

export const GRADE_KO: Record<Grade, string> = {
  SAFE: "안전",
  CAUTION: "주의",
  DANGER: "위험",
};

export const ACTIVITIES: Activity[] = ["레저", "조업", "갯바위", "물놀이"];
