import type { Activity, Briefing, Overview } from "../types";

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
