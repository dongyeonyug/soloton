import type { Advisory, Briefing, DataStatus, FilledNumber, MissingReason, RuleEvidence } from "../types";
import { formatKstDateTime } from "../utils/time";

const STATUS_LABEL: Record<DataStatus, string> = {
  observed: "실측",
  forecast: "예보",
  available: "값 확인됨",
  missing: "정보없음",
  stale: "시간 경과",
};

const STATUS_NOTE: Partial<Record<DataStatus, string>> = {
  missing: "값이 없어 추정하지 않습니다.",
  stale: "관측 시각이 신선도 기준을 넘어 사용하지 않습니다.",
};

const MISSING_REASON_NOTE: Record<MissingReason, string> = {
  source_not_supported: "현재 데이터 소스가 이 지표를 제공하지 않습니다.",
  no_station_mapping: "연결된 관측소 정보가 없어 조회하지 못했습니다.",
  source_returned_no_value: "조회는 했지만 현재 값이 응답에 없었습니다.",
  source_unavailable: "데이터 소스에 연결하지 못했습니다.",
  source_timeout: "정해진 수집 시간 안에 응답하지 않았습니다.",
  legacy_unknown: "이전 스냅샷에는 결측 원인이 기록되지 않았습니다.",
};

const EVIDENCE_LABEL: Record<RuleEvidence, string> = {
  official_baseline: "공식 기준",
  conservative_mapping: "보수 매핑",
};

function metricRole(citation: FilledNumber): string {
  if (citation.is_reference) return "참고값 · 등급 비반영";
  if (citation.is_critical) {
    return citation.is_missing ? "핵심값 없음 · 안전 판정 불가" : "핵심값 · 위험도 반영";
  }
  return citation.is_missing ? "위험도 입력 없음" : "위험도 반영";
}

function metricValue(citation: FilledNumber): string {
  if (citation.is_missing || citation.value === null) return "정보없음";
  const value = Number.isInteger(citation.value) ? citation.value : citation.value.toFixed(1);
  return `${value}${citation.unit}`;
}

function referenceStationNote(citation: FilledNumber): string {
  if (!citation.reference_station_name) return "";
  const code = citation.reference_station_code ? ` (${citation.reference_station_code})` : "";
  const distance = citation.reference_distance_km === null
    ? ""
    : ` · 지점에서 약 ${citation.reference_distance_km}km`;
  return ` · 참고 관측소: ${citation.reference_station_name}${code}${distance}`;
}

function advisoryLabel(advisory: Advisory): string {
  if (advisory.is_missing) return advisory.is_stale ? "시간 경과" : "정보없음";
  return advisory.kind === "none" ? "특보 없음" : advisory.kind;
}

function advisoryRole(advisory: Advisory): string {
  if (advisory.is_missing) return "핵심 정보 없음 · 안전 판정 불가";
  return advisory.kind === "none" ? "위험도 확인 완료" : "위험도를 올리는 요인";
}

/** 데이터의 상태·시점·위험도 역할을 한 표에서 읽게 하는 T3 근거 패널. */
export function DataStatusPanel({ briefing }: { briefing: Briefing }) {
  const summary = briefing.has_missing_critical
    ? "핵심 정보가 없어 안전으로 판정하지 않고 보수적으로 처리했습니다."
    : briefing.is_confession
      ? "일부 위험도 입력이 없지만, 핵심 정보는 확인된 상태입니다."
      : "파고·풍속만 위험도에 반영합니다. 조류·조위·수온은 참고값입니다.";

  return (
    <section className="data-status" aria-labelledby="data-status-title">
      <div className="data-status-heading">
        <div>
          <h3 id="data-status-title">지표별 데이터 상태</h3>
          <p>{summary}</p>
        </div>
      </div>

      <ul className="data-status-list">
        {briefing.citations.map((citation) => (
          <li className={`data-status-row status-${citation.data_status}`} key={citation.label}>
            <div className="data-status-main">
              <div className="data-status-labels">
                <strong>{citation.label}</strong>
                <span className="data-status-badge">{STATUS_LABEL[citation.data_status]}</span>
                <span className="data-role">{metricRole(citation)}</span>
              </div>
              <strong className="data-status-value">{metricValue(citation)}</strong>
            </div>
            <p className="data-status-meta">
              {citation.is_missing
                ? `${citation.checked_source ? `확인 출처: ${citation.checked_source}` : "확인 출처 정보없음"} · ${citation.missing_reason ? MISSING_REASON_NOTE[citation.missing_reason] : STATUS_NOTE[citation.data_status] ?? "값이 없어 사용하지 않습니다."}`
                : `출처: ${citation.observed_source || citation.checked_source || "정보없음"} · 기준 시각 ${formatKstDateTime(citation.observed_at)}`}
              {citation.criterion ? ` · 판단 기준: ${citation.criterion}` : ""}
              {citation.rule_evidence ? ` · ${EVIDENCE_LABEL[citation.rule_evidence]}` : ""}
              {citation.reference_note ? ` · ${citation.reference_note}` : ""}
              {referenceStationNote(citation)}
            </p>
          </li>
        ))}
      </ul>

      {briefing.advisory && (
        <div className={`advisory-status ${briefing.advisory.is_missing ? "is-missing" : ""}`}>
          <div className="data-status-main">
            <div className="data-status-labels">
              <strong>기상특보</strong>
              <span className="data-status-badge">{advisoryLabel(briefing.advisory)}</span>
              <span className="data-role">{advisoryRole(briefing.advisory)}</span>
            </div>
          </div>
          <p className="data-status-meta">
            {briefing.advisory.is_missing
              ? `${briefing.advisory.source || "확인 출처 정보없음"} · 특보 정보를 확인하지 못해 안전으로 판정하지 않습니다.`
              : `${briefing.advisory.source} · ${briefing.advisory.effective_at ? `발효 시각 ${formatKstDateTime(briefing.advisory.effective_at)}` : "현재 특보 없음"}`}
          </p>
        </div>
      )}
    </section>
  );
}
