import { formatKstDateTime } from "../utils/time";

interface Props {
  snapshotAsOf: string | null;
  onPlanStart: () => void;
}

/**
 * 첫 화면의 계획 질문 Hero. 데이터 요청 없이 질문·신뢰 설명·CTA만 담당한다.
 *
 * 기준 시각은 실제 snapshot_as_of 가 있을 때만 말한다 — 확인되지 않은
 * "현재", "최신" 같은 문구를 만들지 않는다.
 */
export function HeroIntro({ snapshotAsOf, onPlanStart }: Props) {
  return (
    <header className="hero-intro">
      <div className="hero-copy">
        <p className="eyebrow">부산 연안 물놀이 계획 확인</p>
        <h1>오늘 바다에서 무엇을 할 예정인가요?</h1>
        <p className="hero-lead">
          장소와 시간을 고르면 그 시각의 예보와 지금 발효 중인 특보를 나눠 정리해 드립니다.
          실제 활동 전에는 공식 기관과 현장 안내를 함께 확인하세요.
        </p>

        <div className="hero-actions" aria-label="주요 행동">
          <button type="button" className="hero-primary" onClick={onPlanStart}>
            내 계획 확인하기
          </button>
          <a className="hero-secondary" href="#/verify">
            AI가 숫자를 못 만드는 방식 보기
          </a>
        </div>

        <p className="hero-trust">
          수치는 코드가 계산합니다. AI는 숫자 없이 쉬운 문장으로만 옮깁니다.
          {snapshotAsOf && ` 자료 기준 시각 ${formatKstDateTime(snapshotAsOf)}.`}
        </p>
      </div>
    </header>
  );
}
