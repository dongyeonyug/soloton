import { HeroIntro } from "./HeroIntro";
import { PlanBriefingPanel } from "./PlanBriefing";
import { PlanComposer } from "./PlanComposer";
import type { PlanBriefing, PlanOptions, SpotOverview } from "../types";

interface Props {
  spots: SpotOverview[];
  selectedSpotId: string | null;
  selectedSpotName: string | null;
  snapshotAsOf: string | null;
  options: PlanOptions | null;
  selectedTime: string | null;
  briefing: PlanBriefing | null;
  loadingSpots: boolean;
  loadingOptions: boolean;
  loadingBriefing: boolean;
  error: string | null;
  onSpotChange: (spotId: string) => void;
  onTimeChange: (time: string) => void;
  onSubmit: () => void;
  onRetry: () => void;
  onPlanStart: () => void;
  onReselect: () => void;
}

/**
 * 홈 상단의 계획 중심 조합 — 질문 Hero, 문장형 계획 입력, 한 장 브리핑.
 *
 * 데이터 요청과 상태는 App 이 소유하고, 이 컴포넌트는 배치만 담당한다.
 */
export function PlanLanding({
  spots,
  selectedSpotId,
  selectedSpotName,
  snapshotAsOf,
  options,
  selectedTime,
  briefing,
  loadingSpots,
  loadingOptions,
  loadingBriefing,
  error,
  onSpotChange,
  onTimeChange,
  onSubmit,
  onRetry,
  onPlanStart,
  onReselect,
}: Props) {
  return (
    <div className="plan-landing">
      {/* 승인 시안의 오프닝 — 데스크톱은 질문(좌)·계획 작성기(우), 모바일은 질문 → 입력 순서 */}
      <div className="plan-opening">
        <HeroIntro snapshotAsOf={snapshotAsOf} onPlanStart={onPlanStart} />

        <PlanComposer
          spots={spots}
          selectedSpotId={selectedSpotId}
          options={options}
          selectedTime={selectedTime}
          loadingSpots={loadingSpots}
          loadingOptions={loadingOptions}
          loadingBriefing={loadingBriefing}
          error={error}
          onSpotChange={onSpotChange}
          onTimeChange={onTimeChange}
          onSubmit={onSubmit}
          onRetry={onRetry}
        />
      </div>

      {/* 상시 존재하는 live region — 결과가 나중에 채워져도 스크린리더가 알아차린다. */}
      <div className="plan-result" aria-live="polite">
        {briefing && (
          <PlanBriefingPanel
            briefing={briefing}
            spotName={selectedSpotName}
            onReselect={onReselect}
          />
        )}
      </div>
    </div>
  );
}
