import type { FilledNumber } from "../types";

/** 근거 수치 칩 — 코드 슬롯필이 소유한 값·출처·시각. LLM 산문 아님.
 *
 * [실측]/[예보] 배지는 백엔드 observed_kind 를 그대로 표시한다(텍스트 병기 — 색만으로
 * 구분하지 않음, WCAG). 결측 값에는 출처를 주장하지 않으므로 배지도 없다.
 */
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
  const kindLabel =
    c.observed_kind === "실측" ? "실제 관측값" : c.observed_kind === "예보" ? "예보 모델값" : "";
  return (
    <span className="chip" aria-label={`${c.label} ${val}${c.unit}${kindLabel ? `, ${kindLabel}` : ""}`}>
      <b>{c.label}</b> {val}
      {c.unit}
      {c.observed_kind && (
        <span
          className={`chip-kind ${c.observed_kind === "예보" ? "chip-kind-forecast" : "chip-kind-observed"}`}
          aria-hidden="true"
        >
          {c.observed_kind}
        </span>
      )}
    </span>
  );
}
