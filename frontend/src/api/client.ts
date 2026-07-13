import type { Activity, Briefing, GuardDemo, GuardVerdict, Overview } from "../types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function fetchOverview(activity: Activity): Promise<Overview> {
  return getJson<Overview>(`/api/overview?activity=${encodeURIComponent(activity)}`);
}

export function fetchBriefing(spotId: string, activity: Activity): Promise<Briefing> {
  return getJson<Briefing>(
    `/api/briefing/${spotId}?activity=${encodeURIComponent(activity)}`,
  );
}

/** E1 — 준비된 시나리오를 실제 가드에 태운 결과. */
export function fetchGuardDemo(): Promise<GuardDemo> {
  return getJson<GuardDemo>("/api/guard/demo");
}

/** E1 — 사용자가 직접 쓴 문장을 같은 가드에 태운다. */
export function checkProse(text: string): Promise<GuardVerdict> {
  return getJson<GuardVerdict>(`/api/guard/check?text=${encodeURIComponent(text)}`);
}
