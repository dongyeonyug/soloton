import type { Advisory, PlanBriefing } from "../types";
import { GRADE_KO } from "../types";
import { formatForecastOption, formatKstDateTime } from "../utils/time";

function advisoryLabel(advisory: Advisory | null): string {
  if (!advisory || advisory.is_missing) return "확인하지 못함";
  return advisory.kind === "none" ? "현재 특보 없음" : advisory.kind;
}

const STATE_LABEL = {
  detailed: "근거 확인됨",
  partial: "일부 정보없음",
  stale: "기준 시각 경과",
  unavailable: "예보 확인 불가",
  invalid_time: "시각 다시 선택",
} as const;

/** 선택 시각 예보와 현재 특보를 한 카드 안에서도 독립된 사실로 보여 준다. */
export function PlanBriefingPanel({ briefing }: { briefing: PlanBriefing }) {
  const conditions = briefing.forecast_conditions;
  const gradeClass = conditions?.grade?.toLowerCase() ?? "partial";

  return (
    <section className="plan-briefing" aria-labelledby="plan-briefing-heading" aria-live="polite">
      <div className="plan-briefing-heading">
        <div>
          <p className="eyebrow">내 물놀이 계획</p>
          <h2 id="plan-briefing-heading">
            {conditions ? formatForecastOption(conditions.forecast_at) : "선택 시각을 다시 확인해 주세요"}
          </h2>
        </div>
        <span className={`plan-state plan-state-${briefing.coverage_state}`}>
          {STATE_LABEL[briefing.coverage_state]}
        </span>
      </div>

      <p className="plan-action">{briefing.action}</p>

      <div className="plan-fact-grid">
        <article className={`plan-fact-card plan-forecast-card grade-${gradeClass}`}>
          <p className="plan-fact-kicker">선택 시각 예보</p>
          {conditions?.grade ? (
            <strong>예보 기준 {GRADE_KO[conditions.grade]}</strong>
          ) : (
            <strong>예보 판단 보류</strong>
          )}
          <p>{conditions?.source ?? "선택한 시각의 예보를 다시 골라 주세요."}</p>
          {conditions && (
            <ul className="plan-citations" aria-label="선택 시각 예보 근거">
              {conditions.citations.map((citation) => (
                <li key={citation.label}>
                  <span>{citation.label}</span>
                  <strong>
                    {citation.is_missing || citation.value === null
                      ? "정보없음"
                      : `${citation.value}${citation.unit}`}
                  </strong>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="plan-fact-card plan-advisory-card">
          <p className="plan-fact-kicker">현재 특보</p>
          <strong>{advisoryLabel(briefing.current_advisory?.advisory ?? null)}</strong>
          <p>{briefing.current_advisory?.scope_label ?? "현재 특보를 확인하지 못했습니다."}</p>
          <small>
            확인 시각 {formatKstDateTime(briefing.current_advisory?.checked_at ?? null)}
          </small>
        </article>
      </div>

      <ul className="plan-limitations">
        {briefing.limitations.map((limitation) => (
          <li key={limitation}>{limitation}</li>
        ))}
      </ul>

      <div className="plan-links" aria-label="공식 확인 경로">
        <h3>출발 전 공식 확인</h3>
        {briefing.official_links.map((link) => (
          <a key={link.url} href={link.url} target="_blank" rel="noreferrer">
            {link.label} <span aria-hidden="true">↗</span>
          </a>
        ))}
      </div>
    </section>
  );
}
