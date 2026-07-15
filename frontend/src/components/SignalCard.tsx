import type { Briefing } from "../types";
import { GRADE_COLOR, GRADE_KO } from "../types";

/** 신호등 카드 (AC7) — 등급을 3색 신호로. */
export function SignalCard({ briefing }: { briefing: Briefing }) {
  const grade = briefing.grade.toLowerCase();
  return (
    <div className={`signal-card grade-${grade}`}>
      <div className="signal-lights">
        {(["SAFE", "CAUTION", "DANGER"] as const).map((g) => (
          <span
            key={g}
            className="light"
            style={{
              background: g === briefing.grade ? GRADE_COLOR[g] : "var(--krds-signal-off)",
            }}
          />
        ))}
      </div>
      <div className={`signal-grade grade-${grade}`}>
        {GRADE_KO[briefing.grade]}
        {briefing.is_confession && <span className="confess-tag">일부 정보없음</span>}
      </div>
    </div>
  );
}
