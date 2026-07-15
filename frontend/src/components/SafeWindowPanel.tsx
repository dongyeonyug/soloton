import type { SafeWindowAssessment, SafeWindowStatus } from "../types";
import { GRADE_KO } from "../types";
import { formatKstDateTime, formatKstHourLabel, formatSafeWindow } from "../utils/time";

const STATUS_TITLE: Record<SafeWindowStatus, string> = {
  available: "시간대 참고",
  forecast_unavailable: "시간대 계산 불가",
  no_future_forecast: "시간대 계산 불가",
  incomplete_forecast: "시간대 계산 불가",
  no_safe_window: "권장 시간대 없음",
};

/** T7: 종료 시각을 단정하지 않고, 예보 기반 참고값 또는 계산 불가 사유를 표시한다. */
export function SafeWindowPanel({ assessment }: { assessment: SafeWindowAssessment | null }) {
  if (!assessment) return null;

  const window = assessment.safe_window;
  const status = assessment.status;
  return (
    <section className={`time-guidance time-${status}`} aria-labelledby="time-guidance-title">
      <div className="time-guidance-heading">
        <h3 id="time-guidance-title">{STATUS_TITLE[status]}</h3>
        <p>{assessment.detail}</p>
      </div>

      {window ? (
        <div className={`safe-window grade-${window.grade.toLowerCase()}`}>
          <span className="safe-window-label">오늘 가장 안전한 시간</span>
          <span className="safe-window-value">
            {formatSafeWindow(window.start, window.end)}
            <span className="safe-window-grade">{GRADE_KO[window.grade]}</span>
          </span>
          <span className="safe-window-deadline">
            활동 종료 참고 시각 <strong>{formatKstHourLabel(window.end)} 이전</strong>
          </span>
          <span className="safe-window-note">
            {assessment.selection_rule} · {assessment.horizon_hours}시간 예보 중 {assessment.forecast_points_graded}/{assessment.forecast_points_considered}개 시각 평가
          </span>
          <span className="safe-window-note">
            종료 참고 시각은 선택 구간의 마지막 예보 시각입니다. 현장 통제와 급격한 파도 변화는 별도로 확인해야 합니다.
          </span>
        </div>
      ) : (
        <p className="time-guidance-empty">시간별 예보가 확인되면 코드가 같은 규칙으로 다시 계산합니다.</p>
      )}

      <p className="time-guidance-meta">
        예보 출처: {assessment.source} · 수집 시각 {formatKstDateTime(assessment.forecast_collected_at)} · 수집 예보 {assessment.forecast_points_collected}개
      </p>
    </section>
  );
}
