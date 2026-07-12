import { useEffect, useState } from "react";
import { fetchBriefing, fetchOverview } from "./api/client";
import { BriefingPanel } from "./components/Briefing";
import { DisclaimerFooter } from "./components/DisclaimerFooter";
import { SignalCard } from "./components/SignalCard";
import { SpotList } from "./components/SpotList";
import { SpotMap } from "./components/SpotMap";
import type { Activity, Briefing, Overview } from "./types";
import { ACTIVITIES } from "./types";

export default function App() {
  const [activity, setActivity] = useState<Activity>("레저");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const retry = () => {
    setError(null);
    setReloadKey((k) => k + 1);
  };

  // 활동 변경 → 개요 재조회 (지도 색칠)
  useEffect(() => {
    setError(null);
    fetchOverview(activity)
      .then((ov) => {
        setOverview(ov);
        setSelected((cur) => cur ?? ov.spots[0]?.id ?? null);
      })
      .catch((e) => {
        console.error(e);
        setError("해양 데이터를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
      });
  }, [activity, reloadKey]);

  // 선택 지점/활동 → 브리핑
  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    fetchBriefing(selected, activity)
      .then(setBriefing)
      .catch((e) => {
        console.error(e);
        setError("브리핑을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
      })
      .finally(() => setLoading(false));
  }, [selected, activity, reloadKey]);

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <p className="eyebrow">부산 연안 해양안전 참고 서비스</p>
          <h1>오늘의 바다</h1>
          <p className="tagline">관측값 기반 활동별 위험도와 근거를 함께 확인합니다.</p>
        </div>
        <div className="activity-tabs" role="group" aria-label="활동 유형 선택">
          {ACTIVITIES.map((a) => (
            <button
              key={a}
              className={a === activity ? "active" : ""}
              aria-pressed={a === activity}
              onClick={() => setActivity(a)}
            >
              {a}
            </button>
          ))}
        </div>
      </header>

      {error && (
        <div className="banner error" role="alert">
          <span>{error}</span>
          <button type="button" className="banner-retry" onClick={retry}>
            다시 시도
          </button>
        </div>
      )}

      <main className="layout">
        <section className="left">
          {overview && (
            <>
              <div className="section-heading">
                <h2>해역 선택</h2>
                <p>지도 또는 목록에서 확인할 지점을 선택하세요.</p>
              </div>
              <SpotMap spots={overview.spots} selected={selected} onSelect={setSelected} />
              <SpotList spots={overview.spots} selected={selected} onSelect={setSelected} />
            </>
          )}
        </section>

        <section className="right" aria-label="선택 지점 브리핑" aria-live="polite">
          {loading && <div className="muted">불러오는 중…</div>}
          {briefing && !loading && (
            <>
              <div className="section-heading briefing-heading">
                <h2>{overview?.spots.find((s) => s.id === selected)?.name}</h2>
                <p>{activity} 활동 기준</p>
              </div>
              <SignalCard briefing={briefing} />
              <BriefingPanel briefing={briefing} />
            </>
          )}
        </section>
      </main>

      <DisclaimerFooter />
    </div>
  );
}
