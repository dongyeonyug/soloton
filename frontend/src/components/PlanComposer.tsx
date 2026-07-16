import type { PlanOptions, SpotOverview } from "../types";
import { formatForecastOption } from "../utils/time";

interface Props {
  spots: SpotOverview[];
  selectedSpotId: string | null;
  options: PlanOptions | null;
  selectedTime: string | null;
  loadingOptions: boolean;
  loadingBriefing: boolean;
  error: string | null;
  onSpotChange: (spotId: string) => void;
  onTimeChange: (time: string) => void;
  onSubmit: () => void;
}

/** Phase 1의 선택형 계획 입력. 자연어를 해석하지 않고 실제 예보 시각만 노출한다. */
export function PlanComposer({
  spots,
  selectedSpotId,
  options,
  selectedTime,
  loadingOptions,
  loadingBriefing,
  error,
  onSpotChange,
  onTimeChange,
  onSubmit,
}: Props) {
  const hasTimes = (options?.forecast_times.length ?? 0) > 0;
  const canSubmit = Boolean(selectedSpotId && selectedTime && !loadingBriefing);

  return (
    <section id="plan-composer" className="plan-composer" aria-labelledby="plan-composer-heading">
      <div className="plan-composer-heading">
        <p className="eyebrow">내 계획 브리핑</p>
        <h2 id="plan-composer-heading">언제, 어디서 물놀이할 예정인가요?</h2>
        <p>선택 시각의 예보와 현재 특보를 나눠 보여드립니다.</p>
      </div>

      <div className="plan-fields">
        <label className="plan-field" htmlFor="plan-spot">
          <span>장소</span>
          <select
            id="plan-spot"
            value={selectedSpotId ?? ""}
            onChange={(event) => onSpotChange(event.target.value)}
          >
            {spots.map((spot) => (
              <option key={spot.id} value={spot.id}>
                {spot.name}
              </option>
            ))}
          </select>
        </label>

        <div className="plan-field plan-time-field">
          <span id="plan-time-label">예정 시각</span>
          {loadingOptions && <p className="plan-field-status">실제 예보 시각을 불러오는 중입니다.</p>}
          {!loadingOptions && !hasTimes && (
            <p className="plan-field-status">선택할 수 있는 미래 예보 시각이 없습니다.</p>
          )}
          {hasTimes && (
            <div className="plan-time-options" aria-labelledby="plan-time-label">
              {options?.forecast_times.map((time) => (
                <button
                  key={time}
                  type="button"
                  className={`plan-time-option${selectedTime === time ? " is-selected" : ""}`}
                  aria-pressed={selectedTime === time}
                  onClick={() => onTimeChange(time)}
                >
                  {formatForecastOption(time)}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {error && (
        <p className="plan-error" role="alert">
          {error}
        </p>
      )}

      <button type="button" className="plan-submit" disabled={!canSubmit} onClick={onSubmit}>
        {loadingBriefing ? "계획을 확인하는 중…" : "내 계획 확인하기"}
      </button>
      <p className="plan-disclaimer">입수 허가나 안전을 보장하지 않습니다. 출발 전 현장 안내를 확인하세요.</p>
    </section>
  );
}
