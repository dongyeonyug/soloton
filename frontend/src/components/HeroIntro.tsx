import type { Briefing, Overview, SpotOverview } from "../types";
import { GRADE_COLOR, GRADE_KO } from "../types";
import { formatKstDateTime } from "../utils/time";

interface Props {
  overview: Overview | null;
  selected: string | null;
  briefing: Briefing | null;
  loading: boolean;
  error: string | null;
  onSpotSelect: () => void;
}

function selectedSpot(overview: Overview | null, selected: string | null): SpotOverview | null {
  if (!overview?.spots.length) return null;
  return overview.spots.find((spot) => spot.id === selected) ?? overview.spots[0] ?? null;
}

function previewTime(overview: Overview | null, briefing: Briefing | null): string {
  return formatKstDateTime(briefing?.snapshot_as_of ?? overview?.snapshot_as_of);
}

function citationStatus(briefing: Briefing): string {
  if (briefing.has_missing_critical) return "핵심 정보없음";
  if (briefing.is_confession) return "일부 정보없음";
  return "근거 확인됨";
}

function PreviewSignal({ spot, briefing }: { spot: SpotOverview; briefing: Briefing | null }) {
  const grade = briefing?.grade ?? spot.grade;
  const gradeClass = grade.toLowerCase();
  const hasMissing = briefing?.is_confession ?? spot.has_missing_critical;

  return (
    <div className={`hero-preview-signal grade-${gradeClass}`}>
      <div className="hero-preview-lights" aria-hidden="true">
        {(["SAFE", "CAUTION", "DANGER"] as const).map((g) => (
          <span
            key={g}
            className="hero-preview-light"
            style={{
              background: g === grade ? GRADE_COLOR[g] : "var(--krds-signal-off)",
            }}
          />
        ))}
      </div>
      <div>
        <strong className={`hero-preview-grade grade-${gradeClass}`}>{GRADE_KO[grade]}</strong>
        {hasMissing && <span className="hero-preview-tag">일부 정보없음</span>}
      </div>
    </div>
  );
}

function PreviewBody({
  overview,
  selected,
  briefing,
  loading,
  error,
}: Omit<Props, "onSpotSelect">) {
  const spot = selectedSpot(overview, selected);

  if (error) {
    return (
      <div className="hero-preview-empty" role="status">
        현재 예시 브리핑을 표시할 수 없습니다.
      </div>
    );
  }

  if (!overview) {
    return (
      <div className="hero-preview-empty" role="status">
        데이터를 불러오는 중입니다. 등급과 기준 시각은 확인된 뒤에만 표시합니다.
      </div>
    );
  }

  if (!spot) {
    return (
      <div className="hero-preview-empty" role="status">
        현재 표시할 지점 정보가 없습니다.
      </div>
    );
  }

  return (
    <>
      <PreviewSignal spot={spot} briefing={briefing} />
      <dl className="hero-preview-facts">
        <div>
          <dt>지점</dt>
          <dd>{spot.name}</dd>
        </div>
        <div>
          <dt>기준 시각</dt>
          <dd>{previewTime(overview, briefing)}</dd>
        </div>
        <div>
          <dt>근거</dt>
          <dd>{briefing ? citationStatus(briefing) : "브리핑 불러오는 중"}</dd>
        </div>
      </dl>
      {loading && (
        <p className="hero-preview-note" role="status">
          선택 지점 브리핑을 불러오는 중입니다.
        </p>
      )}
      {briefing && (
        <div className="hero-preview-citations" aria-label="표시되는 근거 종류">
          {briefing.citations.slice(0, 3).map((citation) => (
            <span
              key={citation.label}
              className={`hero-preview-chip${citation.is_missing ? " is-missing" : ""}`}
            >
              {citation.label} · {citation.is_missing ? "정보없음" : citation.observed_kind || "확인됨"}
            </span>
          ))}
        </div>
      )}
    </>
  );
}

export function HeroIntro({ overview, selected, briefing, loading, error, onSpotSelect }: Props) {
  const spot = selectedSpot(overview, selected);
  const title = !overview
    ? "예시 브리핑 · 데이터를 불러오는 중"
    : spot
      ? `예시 브리핑 · ${spot.name} · 기준 시각 ${previewTime(overview, briefing)}`
      : "예시 브리핑 · 표시할 지점 정보없음";

  return (
    <header className="hero-intro">
      <div className="hero-copy">
        <p className="eyebrow">부산 해안 활동 전 30초 확인</p>
        <h1>바다 가기 전, 지금 지점의 참고 등급을 신호등처럼 확인하세요</h1>
        <p className="hero-lead">
          파고·풍속·특보 같은 공개 해양 정보를 모아 안전/주의/위험 참고 등급과 근거를
          보여줍니다. 실제 활동 전 공식 기관의 최신 안내를 함께 확인하세요.
        </p>

        <div className="hero-actions" aria-label="주요 행동">
          <button type="button" className="hero-primary" onClick={onSpotSelect}>
            지점 선택하기
          </button>
          <a className="hero-secondary" href="#/verify">
            AI가 숫자를 못 만드는 방식 보기
          </a>
        </div>

        <ul className="hero-proof" aria-label="서비스 확인 흐름">
          <li>
            <strong>지점 선택</strong>
            <span>부산 연안 대표 지점</span>
          </li>
          <li>
            <strong>참고 등급</strong>
            <span>코드가 계산한 신호등</span>
          </li>
          <li>
            <strong>근거 확인</strong>
            <span>수치·출처·정보없음 표시</span>
          </li>
        </ul>
      </div>

      <aside className="hero-preview" aria-label="실제 데이터 기반 예시 브리핑">
        <p className="hero-preview-title">{title}</p>
        <PreviewBody
          overview={overview}
          selected={selected}
          briefing={briefing}
          loading={loading}
          error={error}
        />
        <p className="hero-trust">
          수치는 코드가 계산합니다. AI는 숫자 없이 쉬운 문장으로만 옮깁니다.
        </p>
      </aside>
    </header>
  );
}
