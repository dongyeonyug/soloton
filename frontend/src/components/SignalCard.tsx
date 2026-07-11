import type { Briefing } from "../types";
import { GRADE_COLOR, GRADE_KO } from "../types";

/** 신호등 카드 (AC7) — 등급을 3색 신호로. */
export function SignalCard({ briefing }: { briefing: Briefing }) {
  const color = GRADE_COLOR[briefing.grade];
  return (
    <div className="signal-card" style={{ borderColor: color }}>
      <div className="signal-lights">
        {(["SAFE", "CAUTION", "DANGER"] as const).map((g) => (
          <span
            key={g}
            className="light"
            style={{
              background: g === briefing.grade ? GRADE_COLOR[g] : "#2a2f38",
              boxShadow: g === briefing.grade ? `0 0 14px ${GRADE_COLOR[g]}` : "none",
            }}
          />
        ))}
      </div>
      <div className="signal-grade" style={{ color }}>
        {GRADE_KO[briefing.grade]}
        {briefing.is_confession && <span className="confess-tag">일부 정보없음</span>}
      </div>
      <div className="signal-activity">{briefing.activity} 기준</div>
    </div>
  );
}
