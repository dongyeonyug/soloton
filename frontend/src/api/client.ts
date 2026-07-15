import type { Briefing, GuardDemo, GuardVerdict, Overview } from "../types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function fetchOverview(): Promise<Overview> {
  return getJson<Overview>("/api/overview");
}

export function fetchBriefing(spotId: string): Promise<Briefing> {
  return getJson<Briefing>(`/api/briefing/${spotId}`);
}

/** E1 — 준비된 시나리오를 실제 가드에 태운 결과. */
export function fetchGuardDemo(): Promise<GuardDemo> {
  return getJson<GuardDemo>("/api/guard/demo");
}

/** E1 — 사용자가 직접 쓴 문장을 같은 가드에 태운다. */
export function checkProse(text: string): Promise<GuardVerdict> {
  return getJson<GuardVerdict>(`/api/guard/check?text=${encodeURIComponent(text)}`);
}
