import { Fragment } from "react";
import type { Briefing } from "../types";
import { CitationChip } from "./CitationChip";
import { formatKstDateTime } from "../utils/time";

/** 근거 병기 브리핑 (AC8) — 근거 수치 칩 + 숫자없는 AI 산문 + 권고. */
export function BriefingPanel({ briefing }: { briefing: Briefing }) {
  return (
    <div className="briefing">
      <div className="citations">
        {briefing.citations.map((c) => (
          <CitationChip key={c.label} c={c} />
        ))}
      </div>

      {briefing.citations.some((c) => c.source) && (
        <details className="citation-basis">
          <summary>수치 판단 기준</summary>
          <dl>
            {briefing.citations.map((c) =>
              c.source ? (
                <Fragment key={c.label}>
                  <dt>{c.label}</dt>
                  <dd>{c.source}</dd>
                </Fragment>
              ) : null,
            )}
          </dl>
        </details>
      )}

      <p className="prose">
        {briefing.llm_prose}
        <span className={`prose-badge ${briefing.llm_used ? "ai" : "tpl"}`}>
          {briefing.llm_used ? "AI 문장" : "기본 안내"}
        </span>
      </p>

      <ul className="recs">
        {briefing.recommendations.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>

      <div className="asof">
        기준 시각 {formatKstDateTime(briefing.snapshot_as_of)} ·
        수치는 코드가 보장, AI는 표현만
      </div>
    </div>
  );
}
