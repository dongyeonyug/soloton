import { BriefingPanel } from "./Briefing";
import { SignalCard } from "./SignalCard";
import { SpotList } from "./SpotList";
import { SpotMap } from "./SpotMap";
import type { Briefing, Overview } from "../types";

interface Props {
  overview: Overview | null;
  selected: string | null;
  onSelect: (id: string) => void;
  briefing: Briefing | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

/**
 * 보조 해역 현황 — 지도, 지점 목록, 선택 지점의 현재 브리핑.
 *
 * 첫 화면의 주인공은 계획 브리핑이고, 이 섹션은 그 아래의 명확한 2차 영역이다.
 * 지도·목록의 지점 선택은 계획 입력과 같은 `selected` 상태를 공유한다.
 */
export function HomeView({ overview, selected, onSelect, briefing, loading, error, onRetry }: Props) {
  return (
    <section className="sea-status" aria-labelledby="sea-status-heading">
      <div className="section-heading sea-status-heading">
        <h2 id="sea-status-heading">해역 현황 더 보기</h2>
        <p>계획과 별개로, 부산 연안 지점의 현재 참고 등급을 지도와 목록으로 확인할 수 있습니다.</p>
      </div>

      {error && (
        <div className="banner error" role="alert">
          <span>{error}</span>
          <button type="button" className="banner-retry" onClick={onRetry}>
            다시 시도
          </button>
        </div>
      )}

      <div className="layout">
        <div className="left" id="spot-selection" aria-labelledby="spot-selection-heading">
          <div className="section-heading">
            <h3 id="spot-selection-heading" tabIndex={-1}>
              해역 선택
            </h3>
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
        </div>

        <div className="right" aria-label="선택 지점 현재 브리핑" aria-live="polite">
          {loading && <div className="muted">불러오는 중…</div>}
          {!loading && !briefing && !error && (
            <div className="muted">지점을 선택하면 참고 등급과 근거가 표시됩니다.</div>
          )}
          {briefing && !loading && (
            <>
              <div className="section-heading briefing-heading">
                <h3>{overview?.spots.find((s) => s.id === selected)?.name}</h3>
                <p>공식 해양 정보 기반 해안 활동 참고</p>
              </div>
              <SignalCard briefing={briefing} />
              <BriefingPanel briefing={briefing} />
            </>
          )}
        </div>
      </div>
    </section>
  );
}
