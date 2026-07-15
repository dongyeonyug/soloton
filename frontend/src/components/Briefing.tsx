import type { Briefing } from "../types";
import { CitationChip } from "./CitationChip";
import { DataStatusPanel } from "./DataStatusPanel";
import { DecisionPathPanel } from "./DecisionPathPanel";
import { SafeWindowPanel } from "./SafeWindowPanel";
import { formatKstDateTime } from "../utils/time";

const PROSE_STATUS_LABEL = {
  verified: "검증 통과 문장",
  blocked_by_guard: "가드 차단 · 기본 안내",
  generation_unavailable: "생성 불가 · 기본 안내",
  deterministic_fallback: "코드 안내",
} as const;

/** 근거 병기 브리핑 (AC8) — 근거 수치 칩 + 숫자없는 AI 산문 + 권고. */
export function BriefingPanel({ briefing }: { briefing: Briefing }) {
  return (
    <div className="briefing">
      <div className="citations">
        {briefing.citations.map((c) => (
          <CitationChip key={c.label} c={c} />
        ))}
      </div>

      <DataStatusPanel briefing={briefing} />
      <DecisionPathPanel briefing={briefing} />

      <p className="prose">
        {briefing.llm_prose}
        <span className={`prose-badge ${briefing.prose_status === "verified" ? "ai" : "tpl"}`}>
          {PROSE_STATUS_LABEL[briefing.prose_status]}
        </span>
      </p>

      <SafeWindowPanel assessment={briefing.safe_window_assessment} />

      <ul className="recs">
        {briefing.recommendations.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>

      <div className="asof">
        기준 시각 {formatKstDateTime(briefing.snapshot_as_of)} ·
        수치는 코드가 보장, AI는 표현만 · <a href="#/verify">직접 확인하기</a>
      </div>
    </div>
  );
}
