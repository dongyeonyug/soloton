import type { Briefing, RuleEvidence } from "../types";
import { GRADE_KO } from "../types";

const EVIDENCE_LABEL: Record<RuleEvidence, string> = {
  official_baseline: "공식 기준",
  conservative_mapping: "보수 매핑",
};

/** T5: 위험 엔진이 만든 중간 결과를 그대로 표시한다. */
export function DecisionPathPanel({ briefing }: { briefing: Briefing }) {
  return (
    <section className="decision-path" aria-labelledby="decision-path-title">
      <div className="decision-path-heading">
        <h3 id="decision-path-title">위험도 계산 경로</h3>
        <p>코드가 각 입력을 비교해 최종 등급을 계산합니다.</p>
      </div>
      <ol className="decision-steps">
        {briefing.decision_steps.map((step, index) => (
          <li className="decision-step" key={`${step.label}-${index}`}>
            <div className="decision-step-main">
              <strong>{step.label}</strong>
              {step.result_grade && (
                <span className={`decision-grade grade-${step.result_grade.toLowerCase()}`}>
                  {GRADE_KO[step.result_grade]}
                </span>
              )}
              {step.rule_evidence && (
                <span className="decision-evidence">{EVIDENCE_LABEL[step.rule_evidence]}</span>
              )}
            </div>
            <p>{step.detail}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
