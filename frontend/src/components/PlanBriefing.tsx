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

interface PlanBriefingPanelProps {
  briefing: PlanBriefing;
  spotName: string | null;
  onReselect: () => void;
}

/**
 * 판단 중심의 한 장 계획 브리핑.
 *
 * 백엔드 `action`이 중심 문장이고, 선택 시각 예보와 현재 특보는
 * 한 화면 안에서도 독립된 사실로 분리해 보여 준다. UI는 안전 판단이나
 * 수치를 새로 만들지 않는다.
 */
export function PlanBriefingPanel({ briefing, spotName, onReselect }: PlanBriefingPanelProps) {
  const conditions = briefing.forecast_conditions;
  // 등급 강조는 detailed 에서만 — partial/stale/unavailable/invalid_time 이
  // 안전처럼 보이면 안 된다는 상태 계약. 근거 수치와 출처는 그대로 보인다.
  const showGrade = briefing.coverage_state === "detailed" && Boolean(conditions?.grade);
  const gradeClass = showGrade && conditions?.grade ? conditions.grade.toLowerCase() : "partial";
  const invalidTime = briefing.coverage_state === "invalid_time";
  const planTimeLabel = formatForecastOption(conditions?.forecast_at ?? briefing.requested_at);

  return (
    <section className="plan-briefing" aria-labelledby="plan-briefing-heading">
      <div className="plan-briefing-heading">
        <div>
          <p className="eyebrow">내 계획 브리핑</p>
          <h2 id="plan-briefing-heading">
            {spotName ? `${spotName} · ${planTimeLabel}` : planTimeLabel}
          </h2>
        </div>
        <span className={`plan-state plan-state-${briefing.coverage_state}`}>
          {STATE_LABEL[briefing.coverage_state]}
        </span>
      </div>

      <p className="plan-action">{briefing.action}</p>

      {invalidTime && (
        <button type="button" className="plan-reselect" onClick={onReselect}>
          시간 다시 선택하기
        </button>
      )}

      <div className="plan-fact-grid">
        <article className={`plan-fact-card plan-forecast-card grade-${gradeClass}`}>
          <p className="plan-fact-kicker">선택 시각 예보</p>
          {showGrade && conditions?.grade ? (
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
          <small>확인 시각 {formatKstDateTime(briefing.current_advisory?.checked_at ?? null)}</small>
        </article>
      </div>

      <div className="plan-checklist" aria-label="출발 전 확인할 것">
        <h3>출발 전 확인할 것</h3>
        <ul className="plan-limitations">
          {briefing.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </div>

      <div className="plan-links" aria-label="공식 확인 경로">
        <h3>공식 확인 경로</h3>
        {briefing.official_links.map((link) => (
          <a key={link.url} href={link.url} target="_blank" rel="noreferrer">
            {link.label} <span aria-hidden="true">↗</span>
          </a>
        ))}
      </div>
    </section>
  );
}
