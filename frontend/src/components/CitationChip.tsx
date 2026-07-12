import type { FilledNumber } from "../types";

/** 근거 수치 칩 — 코드 슬롯필이 소유한 값·출처·시각. LLM 산문 아님. */
export function CitationChip({ c }: { c: FilledNumber }) {
  if (c.is_missing || c.value === null) {
    return (
      <span
        className="chip chip-missing"
        aria-label={`${c.label} 정보없음. 관측값이 없어 추정하지 않습니다.`}
      >
        {c.label} 정보없음
      </span>
    );
  }
  const val = Number.isInteger(c.value) ? c.value : c.value.toFixed(1);
  return (
    <span className="chip">
      <b>{c.label}</b> {val}
      {c.unit}
    </span>
  );
}
