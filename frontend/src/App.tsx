import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchBriefing,
  fetchOverview,
  fetchPlanBriefing,
  fetchPlanOptions,
} from "./api/client";
import { DisclaimerFooter } from "./components/DisclaimerFooter";
import { GuardDemoPage } from "./components/GuardDemo";
import { HeroIntro } from "./components/HeroIntro";
import { HomeView } from "./components/HomeView";
import { PrincipleSection } from "./components/Principle";
import type { Briefing, Overview, PlanBriefing, PlanOptions } from "./types";
import { forecastTimeToKstOffset } from "./utils/time";

type Route = "home" | "verify";

const readRoute = (): Route =>
  window.location.hash.replace(/^#\/?/, "") === "verify" ? "verify" : "home";

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

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
  const [planOptions, setPlanOptions] = useState<PlanOptions | null>(null);
  const [planTime, setPlanTime] = useState<string | null>(null);
  const [planBriefing, setPlanBriefing] = useState<PlanBriefing | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planOptionsLoading, setPlanOptionsLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);

  const routeRef = useRef<HTMLDivElement>(null);
  const firstRender = useRef(true);
  const planOptionsCache = useRef(new Map<string, PlanOptions>());
  const planRequest = useRef<AbortController | null>(null);
  const planRequestVersion = useRef(0);

  const retry = () => {
    setError(null);
    setPlanError(null);
    planOptionsCache.current.clear();
    setReloadKey((k) => k + 1);
  };

  const focusPlanComposer = () => {
    window.history.replaceState(null, "", "#plan-composer");
    requestAnimationFrame(() => {
      const target = document.getElementById("plan-composer-heading");
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
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchBriefing(selected, controller.signal)
      .then((nextBriefing) => {
        if (!controller.signal.aborted) setBriefing(nextBriefing);
      })
      .catch((e) => {
        if (isAbortError(e)) return;
        console.error(e);
        setError("브리핑을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [selected, reloadKey]);

  // 장소별 실제 예보 시각은 세션 동안 재사용한다. 새 장소를 고르면 이전 계획 결과는 폐기한다.
  useEffect(() => {
    planRequest.current?.abort();
    setPlanBriefing(null);
    setPlanTime(null);
    setPlanError(null);
    if (!selected) {
      setPlanOptions(null);
      return;
    }

    const cached = planOptionsCache.current.get(selected);
    if (cached) {
      setPlanOptions(cached);
      setPlanOptionsLoading(false);
      return;
    }

    const controller = new AbortController();
    setPlanOptions(null);
    setPlanOptionsLoading(true);
    fetchPlanOptions(selected, controller.signal)
      .then((options) => {
        if (controller.signal.aborted) return;
        planOptionsCache.current.set(selected, options);
        setPlanOptions(options);
      })
      .catch((e) => {
        if (isAbortError(e)) return;
        console.error(e);
        setPlanError("선택 가능한 예보 시각을 불러오지 못했어요. 장소를 다시 선택해 주세요.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setPlanOptionsLoading(false);
      });
    return () => controller.abort();
  }, [selected, reloadKey]);

  const selectPlanTime = useCallback((time: string) => {
    planRequest.current?.abort();
    setPlanTime(time);
    setPlanBriefing(null);
    setPlanError(null);
    setPlanLoading(false);
  }, []);

  const submitPlan = useCallback(() => {
    if (!selected || !planTime) return;
    planRequest.current?.abort();
    const controller = new AbortController();
    const version = planRequestVersion.current + 1;
    planRequestVersion.current = version;
    planRequest.current = controller;
    setPlanLoading(true);
    setPlanError(null);

    fetchPlanBriefing(
      {
        spot_id: selected,
        activity: "water_play",
        requested_at: forecastTimeToKstOffset(planTime),
      },
      controller.signal,
    )
      .then((nextBriefing) => {
        if (controller.signal.aborted || version !== planRequestVersion.current) return;
        setPlanBriefing(nextBriefing);
      })
      .catch((e) => {
        if (isAbortError(e) || version !== planRequestVersion.current) return;
        console.error(e);
        setPlanError("계획 브리핑을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
      })
      .finally(() => {
        if (!controller.signal.aborted && version === planRequestVersion.current) {
          setPlanLoading(false);
        }
      });
  }, [planTime, selected]);

  useEffect(() => () => planRequest.current?.abort(), []);

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
          onSpotSelect={focusPlanComposer}
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
            planOptions={planOptions}
            planTime={planTime}
            planBriefing={planBriefing}
            planLoading={planLoading}
            planOptionsLoading={planOptionsLoading}
            planError={planError}
            onPlanTimeChange={selectPlanTime}
            onPlanSubmit={submitPlan}
          />
        )}
      </div>

      <DisclaimerFooter />
    </div>
  );
}
