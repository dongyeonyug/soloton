const KST_TIME_ZONE = "Asia/Seoul";

function parseApiDateTime(value: string): Date {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

export function formatKstDateTime(value: string | null | undefined): string {
  if (!value) {
    return "정보없음";
  }

  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) {
    return "정보없음";
  }

  const parts = new Intl.DateTimeFormat("ko-KR", {
    timeZone: KST_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);

  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";

  return `${pick("year")}-${pick("month")}-${pick("day")} ${pick("hour")}:${pick("minute")}`;
}

/**
 * 예보 시각(KST naive, 예: "2026-07-12T15:00:00")을 "오후 3시" 라벨로.
 * safe_window 시각은 이미 KST 벽시계값이므로 timezone 변환 없이 시(hour)만 읽는다
 * (formatKstDateTime 은 UTC→KST 변환을 하므로 여기 재사용하면 +9 이중 이동 버그).
 */
export function formatKstHourLabel(value: string | null | undefined): string {
  if (!value) {
    return "정보없음";
  }
  const match = /T(\d{2}):/.exec(value);
  if (!match) {
    return "정보없음";
  }
  const hour = Number(match[1]);
  const period = hour < 12 ? "오전" : "오후";
  const hour12 = hour % 12 === 0 ? 12 : hour % 12;
  return `${period} ${hour12}시`;
}

/** KST naive 예보 시각을 선택칩에 쓸 날짜·시간 문장으로. */
export function formatForecastOption(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value);
  if (!match) return "정보없음";
  const [, , month, day] = match;
  return `${Number(month)}월 ${Number(day)}일 ${formatKstHourLabel(value)}`;
}

/** API가 요구하는 +09:00 시각. 예보 시각은 이미 KST 벽시계값이다. */
export function forecastTimeToKstOffset(value: string): string {
  return /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}+09:00`;
}

/** 안전창 시간대 라벨. 시작=끝이면 단일 시각, 아니면 범위. */
export function formatSafeWindow(start: string, end: string): string {
  const startLabel = formatKstHourLabel(start);
  const endLabel = formatKstHourLabel(end);
  return startLabel === endLabel ? startLabel : `${startLabel}~${endLabel}`;
}
