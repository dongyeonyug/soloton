import { useEffect, useRef, useState } from "react";
import { fetchBriefing, fetchOverview } from "./api/client";
import { DisclaimerFooter } from "./components/DisclaimerFooter";
import { GuardDemoPage } from "./components/GuardDemo";
import { HeroIntro } from "./components/HeroIntro";
import { HomeView } from "./components/HomeView";
import { PrincipleSection } from "./components/Principle";
import type { Briefing, Overview } from "./types";

type Route = "home" | "verify";

const readRoute = (): Route =>
  window.location.hash.replace(/^#\/?/, "") === "verify" ? "verify" : "home";

/** 의존성 없는 해시 라우팅. `#/verify` 만 별도 화면, 나머지는 기본 화면. */
function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(readRoute);

  useEffect(() => {
    const onHashChange = () => setRoute(readRoute());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return route;
}

export default function App() {
  const route = useHashRoute();
  // 화면 상태는 App 이 소유한다 — 시연 페이지를 다녀와도 고른 지점이 초기화되지 않도록.
  const [overview, setOverview] = useState<Overview | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const routeRef = useRef<HTMLDivElement>(null);
  const firstRender = useRef(true);

  const retry = () => {
    setError(null);
    setReloadKey((k) => k + 1);
  };

  const focusSpotSelection = () => {
    window.history.replaceState(null, "", "#spot-selection");
    requestAnimationFrame(() => {
      const target = document.getElementById("spot-selection-heading");
      const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      target?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
      target?.focus({ preventScroll: true });
    });
  };

  // 개요 재조회 (지도 색칠)
  useEffect(() => {
    setError(null);
    fetchOverview()
      .then((ov) => {
        setOverview(ov);
        setSelected((cur) => cur ?? ov.spots[0]?.id ?? null);
      })
      .catch((e) => {
        console.error(e);
        setError("해양 데이터를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
      });
  }, [reloadKey]);

  // 선택 지점 → 브리핑
  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    fetchBriefing(selected)
      .then(setBriefing)
      .catch((e) => {
        console.error(e);
        setError("브리핑을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
      })
      .finally(() => setLoading(false));
  }, [selected, reloadKey]);

  // 화면 전환 시 위에서부터 읽고, 스크린리더/키보드 포커스도 새 화면으로 옮긴다(WCAG 2.4.3).
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    window.scrollTo(0, 0);
    routeRef.current?.focus();
  }, [route]);

  return (
    <div className="app">
      {route === "home" && (
        <HeroIntro
          overview={overview}
          selected={selected}
          briefing={briefing}
          loading={loading}
          error={error}
          onSpotSelect={focusSpotSelection}
        />
      )}

      <nav className="mainnav" aria-label="주요 화면">
        <a href="#/" aria-current={route === "home" ? "page" : undefined}>
          해역 현황
        </a>
        <a href="#/verify" aria-current={route === "verify" ? "page" : undefined}>
          AI 거짓말 차단
        </a>
      </nav>

      <div className="route" ref={routeRef} tabIndex={-1}>
        {route === "verify" ? (
          // E3(원리) 위에 E1(증거)이 이어진다 — 설명하고, 곧바로 보여준다.
          <>
            <PrincipleSection />
            <GuardDemoPage />
          </>
        ) : (
          <HomeView
            overview={overview}
            selected={selected}
            onSelect={setSelected}
            briefing={briefing}
            loading={loading}
            error={error}
            onRetry={retry}
          />
        )}
      </div>

      <DisclaimerFooter />
    </div>
  );
}
