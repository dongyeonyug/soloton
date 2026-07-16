import { BriefingPanel } from "./Briefing";
import { PlanBriefingPanel } from "./PlanBriefing";
import { PlanComposer } from "./PlanComposer";
import { SignalCard } from "./SignalCard";
import { SpotList } from "./SpotList";
import { SpotMap } from "./SpotMap";
import type { Briefing, Overview, PlanBriefing, PlanOptions } from "../types";

interface Props {
  overview: Overview | null;
  selected: string | null;
  onSelect: (id: string) => void;
  briefing: Briefing | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  planOptions: PlanOptions | null;
  planTime: string | null;
  planBriefing: PlanBriefing | null;
  planLoading: boolean;
  planOptionsLoading: boolean;
  planError: string | null;
  onPlanTimeChange: (time: string) => void;
  onPlanSubmit: () => void;
}

/**
 * 지도 + 지점 목록 + 선택 지점 브리핑 (기본 화면).
 *
 * 상태는 App 이 소유한다 — 시연 페이지를 다녀와도 고른 지점이 유지되도록.
 */
export function HomeView({
  overview,
  selected,
  onSelect,
  briefing,
  loading,
  error,
  onRetry,
  planOptions,
  planTime,
  planBriefing,
  planLoading,
  planOptionsLoading,
  planError,
  onPlanTimeChange,
  onPlanSubmit,
}: Props) {
  return (
    <>
      {error && (
        <div className="banner error" role="alert">
          <span>{error}</span>
          <button type="button" className="banner-retry" onClick={onRetry}>
            다시 시도
          </button>
        </div>
      )}

      <PlanComposer
        spots={overview?.spots ?? []}
        selectedSpotId={selected}
        options={planOptions}
        selectedTime={planTime}
        loadingOptions={planOptionsLoading}
        loadingBriefing={planLoading}
        error={planError}
        onSpotChange={onSelect}
        onTimeChange={onPlanTimeChange}
        onSubmit={onPlanSubmit}
      />

      {planBriefing && <PlanBriefingPanel briefing={planBriefing} />}

      <main className="layout">
        <section className="left" id="spot-selection" aria-labelledby="spot-selection-heading">
          <div className="section-heading">
            <h2 id="spot-selection-heading" tabIndex={-1}>
              해역 선택
            </h2>
            <p>지도 또는 목록에서 확인할 지점을 선택하세요.</p>
          </div>

          {!overview && !error && (
            <p className="spot-list-empty" role="status">
              지점 정보를 불러오는 중입니다.
            </p>
          )}

          {!overview && error && (
            <p className="spot-list-empty" role="status">
              현재 표시할 지점 정보가 없습니다.
            </p>
          )}

          {overview && (
            <>
              <SpotMap spots={overview.spots} selected={selected} onSelect={onSelect} />
              <SpotList spots={overview.spots} selected={selected} onSelect={onSelect} />
            </>
          )}
        </section>

        <section className="right" aria-label="선택 지점 브리핑" aria-live="polite">
          {loading && <div className="muted">불러오는 중…</div>}
          {!loading && !briefing && !error && (
            <div className="muted">지점을 선택하면 참고 등급과 근거가 표시됩니다.</div>
          )}
          {briefing && !loading && (
            <>
              <div className="section-heading briefing-heading">
                <h2>{overview?.spots.find((s) => s.id === selected)?.name}</h2>
                <p>공식 해양 정보 기반 해안 활동 참고</p>
              </div>
              <SignalCard briefing={briefing} />
              <BriefingPanel briefing={briefing} />
            </>
          )}
        </section>
      </main>
    </>
  );
}
