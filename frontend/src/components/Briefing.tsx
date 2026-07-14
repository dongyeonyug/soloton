import { Fragment } from "react";
import type { Briefing } from "../types";
import { GRADE_KO } from "../types";
import { CitationChip } from "./CitationChip";
import { formatKstDateTime, formatSafeWindow } from "../utils/time";

/** 근거 병기 브리핑 (AC8) — 근거 수치 칩 + 숫자없는 AI 산문 + 권고. */
export function BriefingPanel({ briefing }: { briefing: Briefing }) {
  return (
    <div className="briefing">
      <div className="citations">
        {briefing.citations.map((c) => (
          <CitationChip key={c.label} c={c} />
        ))}
      </div>

      {briefing.citations.some((c) => c.observed_source || c.criterion || c.is_reference) && (
        <details className="citation-basis">
          <summary>수치 출처·판단 기준</summary>
          <dl>
            {briefing.citations.map((c) => (
              <Fragment key={c.label}>
                <dt>{c.label}</dt>
                <dd>
                  {c.is_missing
                    ? "정보없음 — 추정하지 않습니다"
                    : `${c.observed_kind ? `[${c.observed_kind}] ` : ""}${c.observed_source}`}
                  {c.is_reference
                    ? " · 참고 지표(등급에 반영되지 않음)"
                    : c.criterion
                      ? ` · 판단 기준: ${c.criterion}`
                      : null}
                </dd>
              </Fragment>
            ))}
          </dl>
        </details>
      )}

      <p className="prose">
        {briefing.llm_prose}
        <span className={`prose-badge ${briefing.llm_used ? "ai" : "tpl"}`}>
          {briefing.llm_used ? "AI 문장" : "기본 안내"}
        </span>
      </p>

      {briefing.safe_window && (
        <div className={`safe-window grade-${briefing.safe_window.grade.toLowerCase()}`}>
          <span className="safe-window-label">오늘 가장 안전한 시간</span>
          <span className="safe-window-value">
            {formatSafeWindow(briefing.safe_window.start, briefing.safe_window.end)}
            <span className="safe-window-grade">
              {GRADE_KO[briefing.safe_window.grade]}
            </span>
          </span>
          <span className="safe-window-note">
            예보 기준 참고값 · 시간은 코드가 계산
          </span>
        </div>
      )}

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
