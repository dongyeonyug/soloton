import { expect, test, type Page } from "@playwright/test";

const SNAPSHOT_AT = "2026-07-20T00:00:00";
const HAEUNDAE_TIME = "2026-07-20T10:00:00";
const GWANGALLI_TIME = "2026-07-20T14:00:00";

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

const forecastCitations = [
  {
    label: "유의파고",
    value: 0.4,
    unit: "m",
    observed_source: "Open-Meteo",
    checked_source: "Open-Meteo",
    observed_kind: "예보",
    criterion: "1.0m 이하",
    rule_evidence: "conservative_mapping",
    observed_at: null,
    is_missing: false,
    missing_reason: null,
    data_status: "forecast",
    is_critical: true,
    is_reference: false,
    reference_note: "",
    reference_station_name: null,
    reference_station_code: null,
    reference_distance_km: null,
  },
  {
    label: "풍속",
    value: 3.2,
    unit: "m/s",
    observed_source: "Open-Meteo",
    checked_source: "Open-Meteo",
    observed_kind: "예보",
    criterion: "6.0m/s 이하",
    rule_evidence: "conservative_mapping",
    observed_at: null,
    is_missing: false,
    missing_reason: null,
    data_status: "forecast",
    is_critical: true,
    is_reference: false,
    reference_note: "",
    reference_station_name: null,
    reference_station_code: null,
    reference_distance_km: null,
  },
];

function planBriefing(requestedAt: string, state: "ready" | "invalid_time") {
  const invalidTime = state === "invalid_time";
  return {
    spot_id: "gwangalli",
    activity: "water_play",
    requested_at: requestedAt,
    data_state: state,
    coverage_state: invalidTime ? "invalid_time" : "detailed",
    forecast_conditions: invalidTime
      ? null
      : {
          forecast_at: requestedAt.replace("+09:00", ""),
          grade: "SAFE",
          citations: forecastCitations,
          has_missing_critical: false,
          source: "Open-Meteo 시간별 예보",
        },
    current_advisory: {
      advisory: {
        kind: "풍랑주의보",
        effective_at: "2026-07-20T05:00:00+09:00",
        source: "기상청",
        is_missing: false,
        is_stale: false,
      },
      checked_at: "2026-07-20T06:00:00+09:00",
      scope_label: "현재 기준 · 미래 보장 아님",
    },
    action: invalidTime
      ? "선택한 예보 시각이 갱신됐습니다. 실제 예보 시각을 다시 선택하세요."
      : "예보상 물놀이 참고 등급은 안전입니다. 출발 전 현장 안내를 다시 확인하세요.",
    limitations: [
      "예보는 현장 통제나 입수 허가를 대신하지 않습니다.",
      "현재 특보는 선택 시각의 미래 상태를 보장하지 않습니다.",
    ],
    official_links: [
      {
        label: "기상청 해양기상 정보",
        url: "https://www.weather.go.kr",
        source_owner: "기상청",
        activity_scope: "water_play",
        region_scope: "대한민국 연안",
        last_verified_at: "2026-07-20T00:00:00+09:00",
        fallback_text: "기상청 해양기상 정보를 확인하세요.",
      },
    ],
    snapshot_as_of: SNAPSHOT_AT,
  };
}

async function mockPlanApi(
  page: Page,
  state: "ready" | "invalid_time",
  submittedRequests: unknown[],
) {
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
      const spotId = path.split("/").at(-1);
      const forecastTime = spotId === "gwangalli" ? GWANGALLI_TIME : HAEUNDAE_TIME;
      await route.fulfill({
        json: {
          spot_id: spotId,
          activity: "water_play",
          forecast_times: [forecastTime],
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
      await route.fulfill({ json: planBriefing(body.requested_at, state) });
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
  await mockPlanApi(page, "ready", submittedRequests);

  await page.goto("/");
  const composer = page.locator("#plan-composer");
  await expect(composer.getByRole("button", { name: "내 계획 확인하기" })).toBeDisabled();

  await chooseGwangalliPlan(page);

  const result = page.locator(".plan-briefing");
  await expect(result).toBeVisible();
  await expect(result.locator(".plan-forecast-card")).toContainText("선택 시각 예보");
  await expect(result.locator(".plan-forecast-card")).toContainText("예보 기준 안전");
  await expect(result.locator(".plan-advisory-card")).toContainText("현재 특보");
  await expect(result.locator(".plan-advisory-card")).toContainText("풍랑주의보");
  await expect(result.locator(".plan-advisory-card")).toContainText("현재 기준 · 미래 보장 아님");
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
  await mockPlanApi(page, "invalid_time", submittedRequests);

  await page.goto("/");
  await chooseGwangalliPlan(page);

  const result = page.locator(".plan-briefing");
  await expect(result.getByRole("heading", { name: "선택 시각을 다시 확인해 주세요" })).toBeVisible();
  await expect(result).toContainText("시각 다시 선택");
  await expect(result.locator(".plan-forecast-card")).toContainText("예보 판단 보류");
  await expect(result.locator(".plan-advisory-card")).toContainText("현재 특보");

  await page.locator("#plan-composer").getByRole("button", { name: "7월 20일 오후 2시" }).click();
  await expect(result).toBeHidden();
  expect(submittedRequests).toHaveLength(1);
});
