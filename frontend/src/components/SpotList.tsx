import type { SpotOverview } from "../types";
import { GRADE_COLOR, GRADE_KO } from "../types";

/** 지점 리스트 (지도 대안 선택 경로, AC7). */
export function SpotList({
  spots,
  selected,
  onSelect,
}: {
  spots: SpotOverview[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <ul className="spot-list">
      {spots.map((s) => (
        <li
          key={s.id}
          className={s.id === selected ? "active" : ""}
        >
          <button type="button" onClick={() => onSelect(s.id)} aria-pressed={s.id === selected}>
            <span className="dot" style={{ background: GRADE_COLOR[s.grade] }} />
            <span className="spot-name">{s.name}</span>
            <span className="spot-grade" style={{ color: GRADE_COLOR[s.grade] }}>
              {GRADE_KO[s.grade]}
              {s.has_missing_critical && " · 정보없음"}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
