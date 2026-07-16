import type {
  Briefing,
  GuardDemo,
  GuardVerdict,
  Overview,
  PlanBriefing,
  PlanIntent,
  PlanOptions,
} from "../types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function fetchOverview(): Promise<Overview> {
  return getJson<Overview>("/api/overview");
}

export function fetchBriefing(spotId: string, signal?: AbortSignal): Promise<Briefing> {
  return getJson<Briefing>(`/api/briefing/${spotId}`, signal);
}

export function fetchPlanOptions(spotId: string, signal?: AbortSignal): Promise<PlanOptions> {
  return getJson<PlanOptions>(`/api/plans/options/${spotId}`, signal);
}

export function fetchPlanBriefing(
  intent: PlanIntent,
  signal?: AbortSignal,
): Promise<PlanBriefing> {
  return postJson<PlanBriefing>("/api/plans/briefing", intent, signal);
}

/** E1 — 준비된 시나리오를 실제 가드에 태운 결과. */
export function fetchGuardDemo(): Promise<GuardDemo> {
  return getJson<GuardDemo>("/api/guard/demo");
}

/** E1 — 사용자가 직접 쓴 문장을 같은 가드에 태운다. */
export function checkProse(text: string): Promise<GuardVerdict> {
  return getJson<GuardVerdict>(`/api/guard/check?text=${encodeURIComponent(text)}`);
}
