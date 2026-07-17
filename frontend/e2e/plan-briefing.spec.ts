import { expect, test, type Page } from "@playwright/test";

const SNAPSHOT_AT = "2026-07-20T00:00:00";
const HAEUNDAE_TIME = "2026-07-20T10:00:00";
const GWANGALLI_TIME = "2026-07-20T14:00:00";
const GWANGALLI_TIME_LATE = "2026-07-20T17:00:00";

type PlanState = "ready" | "invalid_time" | "partial" | "stale" | "unavailable";

const spots = [
  {
    id: "haeundae",
    name: "해운대해수욕장",
    lat: 35.1587,
    lng: 129.1604,
    type: "beach",
    grade: "SAFE",
    grade_ko: "안전",
    has_missing_critical: false,
  },
  {
    id: "gwangalli",
    name: "광안리해수욕장",
    lat: 35.1532,
    lng: 129.1187,
    type: "beach",
    grade: "CAUTION",
    grade_ko: "주의",
    has_missing_critical: false,
  },
];

const legacyBriefing = {
  spot_id: "haeundae",
  time_slot: "현재",
  grade: "SAFE",
  template_text: "참고용 브리핑입니다.",
  llm_prose: "공식 안내를 함께 확인하세요.",
  citations: [],
  recommendations: [],
  is_confession: false,
  has_missing_critical: false,
  advisory: { kind: "none", effective_at: null, source: "기상청", is_missing: false, is_stale: false },
  decision_steps: [],
  prose_status: "deterministic_fallback",
  snapshot_as_of: SNAPSHOT_AT,
  safe_window: null,
  safe_window_assessment: null,
};

function forecastCitation(label: string, value: number | null, unit: string, missing = false) {
  return {
    label,
    value,
    unit,
    observed_source: missing ? "" : "Open-Meteo",
    checked_source: "Open-Meteo",
    observed_kind: missing ? "" : "예보",
    criterion: label === "유의파고" ? "1.0m 이하" : "6.0m/s 이하",
    rule_evidence: "conservative_mapping",
    observed_at: null,
    is_missing: missing,
    missing_reason: missing ? "source_returned_no_value" : null,
    data_status: missing ? "missing" : "forecast",
    is_critical: true,
    is_reference: false,
    reference_note: "",
    reference_station_name: null,
    reference_station_code: null,
    reference_distance_km: null,
  };
}

const currentAdvisory = {
  advisory: {
    kind: "풍랑주의보",
    effective_at: "2026-07-20T05:00:00+09:00",
    source: "기상청",
    is_missing: false,
    is_stale: false,
  },
  checked_at: "2026-07-20T06:00:00+09:00",
  scope_label: "현재 기준 · 미래 보장 아님",
};

const officialLinks = [
  {
    label: "기상청 해양기상 정보",
    url: "https://www.weather.go.kr",
    source_owner: "기상청",
    activity_scope: "water_play",
    region_scope: "대한민국 연안",
    last_verified_at: "2026-07-20T00:00:00+09:00",
    fallback_text: "기상청 해양기상 정보를 확인하세요.",
  },
];

/** 파고·풍속이 모두 있는 SAFE 예보 — ready 와 stale(수집 시각만 경과)이 공유한다. */
function safeForecast(requestedAt: string) {
  return {
    forecast_at: requestedAt.replace("+09:00", ""),
    grade: "SAFE",
    citations: [forecastCitation("유의파고", 0.4, "m"), forecastCitation("풍속", 3.2, "m/s")],
    has_missing_critical: false,
    source: "Open-Meteo 시간별 예보",
  };
}

const STATE_FIXTURE: Record<
  PlanState,
  {
    coverage_state: string;
    action: string;
    forecast: (requestedAt: string) => unknown;
  }
> = {
  ready: {
    coverage_state: "detailed",
    action: "예보상 물놀이 참고 등급은 안전입니다. 출발 전 현장 안내를 다시 확인하세요.",
    forecast: safeForecast,
  },
  invalid_time: {
    coverage_state: "invalid_time",
    action: "선택한 예보 시각이 갱신됐습니다. 실제 예보 시각을 다시 선택하세요.",
    forecast: () => null,
  },
  partial: {
    coverage_state: "partial",
    action: "풍속 예보를 확인하지 못해 판단을 보류합니다. 공식 정보를 확인하세요.",
    forecast: (requestedAt) => ({
      forecast_at: requestedAt.replace("+09:00", ""),
      grade: null,
      citations: [forecastCitation("유의파고", 0.4, "m"), forecastCitation("풍속", null, "m/s", true)],
      has_missing_critical: true,
      source: "Open-Meteo 시간별 예보",
    }),
  },
  stale: {
    coverage_state: "stale",
    action: "예보 기준 시각이 지났습니다. 최신 공식 정보를 다시 확인하세요.",
    forecast: safeForecast,
  },
  unavailable: {
    coverage_state: "unavailable",
    action: "선택한 시각의 예보를 확인하지 못했습니다. 공식 정보를 확인하세요.",
    forecast: () => null,
  },
};

function planBriefing(requestedAt: string, state: PlanState) {
  const fixture = STATE_FIXTURE[state];
  return {
    spot_id: "gwangalli",
    activity: "water_play",
    requested_at: requestedAt,
    data_state: state,
    coverage_state: fixture.coverage_state,
    forecast_conditions: fixture.forecast(requestedAt),
    current_advisory: currentAdvisory,
    action: fixture.action,
    limitations: [
      "예보는 현장 통제나 입수 허가를 대신하지 않습니다.",
      "현재 특보는 선택 시각의 미래 상태를 보장하지 않습니다.",
    ],
    official_links: officialLinks,
    snapshot_as_of: SNAPSHOT_AT,
  };
}

interface MockOptions {
  state?: PlanState;
  optionsFailure?: boolean;
  /** requested_at 별 POST 응답 지연(ms). 늦은 응답이 최신 선택을 덮는지 검증할 때 사용. */
  briefingDelaysMs?: Record<string, number>;
}

async function mockPlanApi(page: Page, submittedRequests: unknown[], mock: MockOptions = {}) {
  const state = mock.state ?? "ready";
  await page.route("http://localhost:8000/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

    if (path === "/api/overview") {
      await route.fulfill({ json: { snapshot_as_of: SNAPSHOT_AT, spots } });
      return;
    }

    if (path.startsWith("/api/briefing/")) {
      await route.fulfill({ json: { ...legacyBriefing, spot_id: path.split("/").at(-1) } });
      return;
    }

    if (path.startsWith("/api/plans/options/")) {
      if (mock.optionsFailure) {
        await route.fulfill({ status: 503, json: { detail: "forecast options unavailable" } });
        return;
      }
      const spotId = path.split("/").at(-1);
      const forecastTimes =
        spotId === "gwangalli" ? [GWANGALLI_TIME, GWANGALLI_TIME_LATE] : [HAEUNDAE_TIME];
      await route.fulfill({
        json: {
          spot_id: spotId,
          activity: "water_play",
          forecast_times: forecastTimes,
          forecast_status: "available",
          forecast_collected_at: SNAPSHOT_AT,
          snapshot_as_of: SNAPSHOT_AT,
        },
      });
      return;
    }

    if (path === "/api/plans/briefing" && request.method() === "POST") {
      const body = request.postDataJSON() as { requested_at: string };
      submittedRequests.push(body);
      const delay = mock.briefingDelaysMs?.[body.requested_at] ?? 0;
      if (delay > 0) {
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
      try {
        await route.fulfill({ json: planBriefing(body.requested_at, state) });
      } catch {
        // 지연 중 클라이언트가 요청을 abort 하면 fulfill 이 실패할 수 있다 — 의도된 경로.
      }
      return;
    }

    await route.fulfill({ status: 404, json: { detail: `Unhandled API route: ${path}` } });
  });
}

async function chooseGwangalliPlan(page: Page) {
  const composer = page.locator("#plan-composer");
  await composer.getByRole("combobox", { name: "장소" }).selectOption("gwangalli");
  const timeButton = composer.getByRole("button", { name: "7월 20일 오후 2시" });
  await expect(timeButton).toBeVisible();
  await timeButton.click();
  await composer.getByRole("button", { name: "내 계획 확인하기" }).click();
}

test("물놀이 계획은 선택 시각 예보와 현재 특보를 분리해 보여준다", async ({ page }) => {
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests);

  await page.goto("/");
  const composer = page.locator("#plan-composer");
  await expect(composer.getByRole("button", { name: "내 계획 확인하기" })).toBeDisabled();
  await expect(composer.getByText("물놀이", { exact: true })).toBeVisible();

  await chooseGwangalliPlan(page);

  const result = page.locator(".plan-briefing");
  await expect(result).toBeVisible();
  await expect(
    result.getByRole("heading", { name: "광안리해수욕장 · 7월 20일 오후 2시" }),
  ).toBeVisible();
  await expect(result.getByText("근거 확인됨")).toBeVisible();
  await expect(result.locator(".plan-action")).toContainText("예보상 물놀이 참고 등급은 안전입니다");
  await expect(result.locator(".plan-forecast-card")).toContainText("선택 시각 예보");
  await expect(result.locator(".plan-forecast-card")).toContainText("예보 기준 안전");
  await expect(result.locator(".plan-advisory-card")).toContainText("현재 특보");
  await expect(result.locator(".plan-advisory-card")).toContainText("풍랑주의보");
  await expect(result.locator(".plan-advisory-card")).toContainText("현재 기준 · 미래 보장 아님");
  await expect(result.getByRole("heading", { name: "출발 전 확인할 것" })).toBeVisible();
  await expect(result.getByRole("link", { name: /기상청 해양기상 정보/ })).toHaveAttribute(
    "href",
    "https://www.weather.go.kr",
  );
  expect(submittedRequests).toEqual([
    { spot_id: "gwangalli", activity: "water_play", requested_at: `${GWANGALLI_TIME}+09:00` },
  ]);
});

test("예보 시각이 제출 사이에 만료되면 안전하게 다시 선택하게 한다", async ({ page }) => {
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests, { state: "invalid_time" });

  await page.goto("/");
  await chooseGwangalliPlan(page);

  const result = page.locator(".plan-briefing");
  await expect(result.getByText("시각 다시 선택")).toBeVisible();
  await expect(result.locator(".plan-forecast-card")).toContainText("예보 판단 보류");
  await expect(result.locator(".plan-advisory-card")).toContainText("현재 특보");

  // 재선택 버튼은 계획 시간 영역으로 포커스를 옮긴다.
  await result.getByRole("button", { name: "시간 다시 선택하기" }).click();
  const firstTimeOption = page.locator("#plan-composer .plan-time-option").first();
  await expect(firstTimeOption).toBeFocused();

  await page.locator("#plan-composer").getByRole("button", { name: "7월 20일 오후 5시" }).click();
  await expect(result).toBeHidden();
  expect(submittedRequests).toHaveLength(1);
});

test("빠르게 시간을 바꿔 다시 제출하면 마지막 선택의 결과만 남는다", async ({ page }) => {
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests, {
    briefingDelaysMs: { [`${GWANGALLI_TIME}+09:00`]: 1500 },
  });

  await page.goto("/");
  const composer = page.locator("#plan-composer");
  await composer.getByRole("combobox", { name: "장소" }).selectOption("gwangalli");

  // 느린 응답이 올 첫 번째 시각을 제출한 직후, 두 번째 시각으로 갈아탄다.
  await composer.getByRole("button", { name: "7월 20일 오후 2시" }).click();
  await composer.getByRole("button", { name: "내 계획 확인하기" }).click();
  await composer.getByRole("button", { name: "7월 20일 오후 5시" }).click();
  await composer.getByRole("button", { name: "내 계획 확인하기" }).click();

  const result = page.locator(".plan-briefing");
  await expect(
    result.getByRole("heading", { name: "광안리해수욕장 · 7월 20일 오후 5시" }),
  ).toBeVisible();

  // 지연된 첫 응답이 도착할 시간을 준 뒤에도 마지막 선택이 유지되어야 한다.
  await page.waitForTimeout(2000);
  await expect(
    result.getByRole("heading", { name: "광안리해수욕장 · 7월 20일 오후 5시" }),
  ).toBeVisible();
  expect(submittedRequests).toHaveLength(2);
});

test("예보 시각 옵션 요청이 실패하면 오류와 다시 시도 경로를 보여준다", async ({ page }) => {
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests, { optionsFailure: true });

  await page.goto("/");
  const composer = page.locator("#plan-composer");
  await expect(composer.getByRole("alert")).toContainText("예보 시각을 불러오지 못했");
  await expect(composer.getByRole("button", { name: "다시 시도" })).toBeVisible();
  // 임의 시간을 만들어 보여주지 않는다.
  await expect(composer.locator(".plan-time-option")).toHaveCount(0);
  await expect(composer.getByRole("button", { name: "내 계획 확인하기" })).toBeDisabled();
  expect(submittedRequests).toHaveLength(0);
});

test("지점 목록 요청이 실패해도 계획 입력 영역에서 오류를 알린다", async ({ page }) => {
  await page.route("http://localhost:8000/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/overview") {
      await route.fulfill({ status: 503, json: { detail: "overview unavailable" } });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: `Unhandled API route: ${path}` } });
  });

  await page.goto("/");
  const composer = page.locator("#plan-composer");
  await expect(composer.getByRole("alert")).toContainText("지점 정보를 불러오지 못했");
  await expect(composer.getByRole("button", { name: "다시 시도" })).toBeVisible();
  // 지점이 없는데 "예보 시각이 없습니다" 같은 오해를 부르는 문구를 쓰지 않는다.
  await expect(composer).not.toContainText("선택할 수 있는 미래 예보 시각이 없습니다");
  await expect(composer.getByRole("button", { name: "내 계획 확인하기" })).toBeDisabled();
});

test("partial 상태는 빠진 근거를 정보없음으로 자백한다", async ({ page }) => {
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests, { state: "partial" });

  await page.goto("/");
  await chooseGwangalliPlan(page);

  const result = page.locator(".plan-briefing");
  await expect(result.getByText("일부 정보없음")).toBeVisible();
  await expect(result.locator(".plan-action")).toContainText("판단을 보류합니다");
  await expect(result.locator(".plan-forecast-card")).toContainText("예보 판단 보류");
  const windRow = result.locator(".plan-citations li", { hasText: "풍속" });
  await expect(windRow).toContainText("정보없음");
  await expect(result.getByRole("link", { name: /기상청 해양기상 정보/ })).toBeVisible();
});

test("stale 상태는 기준 시각 경과를 숨기지 않는다", async ({ page }) => {
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests, { state: "stale" });

  await page.goto("/");
  await chooseGwangalliPlan(page);

  const result = page.locator(".plan-briefing");
  await expect(result.getByText("기준 시각 경과")).toBeVisible();
  await expect(result.locator(".plan-action")).toContainText("예보 기준 시각이 지났습니다");
  // 오래된 등급을 안전처럼 꾸미지 않는다 — 백엔드 grade 가 SAFE 여도 판단을 보류한다.
  await expect(result.locator(".plan-forecast-card")).toContainText("예보 판단 보류");
  await expect(result.locator(".plan-forecast-card strong").first()).not.toContainText("안전");
  await expect(result).not.toContainText("최신 예보");
  await expect(result.getByRole("link", { name: /기상청 해양기상 정보/ })).toBeVisible();
});

test("unavailable 상태는 안전 등급을 만들지 않고 판단을 보류한다", async ({ page }) => {
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests, { state: "unavailable" });

  await page.goto("/");
  await chooseGwangalliPlan(page);

  const result = page.locator(".plan-briefing");
  await expect(result.getByText("예보 확인 불가")).toBeVisible();
  await expect(result.locator(".plan-forecast-card")).toContainText("예보 판단 보류");
  await expect(result.locator(".plan-forecast-card")).not.toContainText("안전");
  await expect(result.getByRole("link", { name: /기상청 해양기상 정보/ })).toBeVisible();
});

test("모바일 375px에서 수평 스크롤 없이 계획 흐름을 완주할 수 있다", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests);

  await page.goto("/");
  await chooseGwangalliPlan(page);

  const result = page.locator(".plan-briefing");
  await expect(
    result.getByRole("heading", { name: "광안리해수욕장 · 7월 20일 오후 2시" }),
  ).toBeVisible();

  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);
});

test("시간 선택·제출·재선택이 키보드만으로 가능하다", async ({ page }) => {
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests, { state: "invalid_time" });

  await page.goto("/");
  const composer = page.locator("#plan-composer");
  await composer.getByRole("combobox", { name: "장소" }).selectOption("gwangalli");

  const timeButton = composer.getByRole("button", { name: "7월 20일 오후 2시" });
  await timeButton.focus();
  await page.keyboard.press("Enter");
  await expect(timeButton).toHaveAttribute("aria-pressed", "true");

  const submit = composer.getByRole("button", { name: "내 계획 확인하기" });
  await submit.focus();
  await page.keyboard.press("Enter");

  const reselect = page.locator(".plan-briefing").getByRole("button", { name: "시간 다시 선택하기" });
  await reselect.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#plan-composer .plan-time-option").first()).toBeFocused();
  expect(submittedRequests).toHaveLength(1);
});

test("기존 #/verify 검증 화면이 회귀하지 않는다", async ({ page }) => {
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests);

  await page.goto("/#/verify");
  await expect(
    page.getByRole("heading", { name: "AI는 이 화면의 숫자를 하나도 만들지 않습니다" }),
  ).toBeVisible();
});

test("보조 해역 현황은 유지되고 계획 장소 선택과 동기화된다", async ({ page }) => {
  const submittedRequests: unknown[] = [];
  await mockPlanApi(page, submittedRequests);

  await page.goto("/");

  // 계획 입력이 보조 현황보다 먼저 읽힌다.
  const domOrder = await page.evaluate(() => {
    const composer = document.getElementById("plan-composer");
    const seaStatus = document.querySelector(".sea-status");
    if (!composer || !seaStatus) return null;
    return Boolean(composer.compareDocumentPosition(seaStatus) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(domOrder).toBe(true);

  const seaStatus = page.locator(".sea-status");
  await expect(seaStatus.getByRole("heading", { name: "해역 현황 더 보기" })).toBeVisible();

  // 목록에서 지점을 고르면 계획 입력의 장소도 함께 바뀐다.
  await seaStatus
    .getByRole("list", { name: "지점 목록 (지도 대체 선택)" })
    .getByRole("button", { name: /광안리해수욕장/ })
    .click();
  await expect(page.locator("#plan-composer").getByRole("combobox", { name: "장소" })).toHaveValue(
    "gwangalli",
  );
  await expect(seaStatus.getByRole("heading", { name: "광안리해수욕장" })).toBeVisible();
});
