import { useEffect, useMemo, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { MapContainer, Marker, TileLayer, Tooltip } from "react-leaflet";
import { divIcon } from "leaflet";
import type { Grade, SpotOverview } from "../types";
import { GRADE_COLOR, GRADE_KO } from "../types";

const BUSAN_CENTER: [number, number] = [35.12, 129.08];

/** 등급별 색 외 형태 단서 (색약·저시력 대비, WCAG 1.4.1). */
const GRADE_SYMBOL: Record<Grade, string> = {
  SAFE: "circle",
  CAUTION: "triangle",
  DANGER: "square",
};

/** prefers-reduced-motion을 구독해 Leaflet 애니메이션을 끈다. */
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/** 등급 형태를 그리는 SVG 마크업 (색 + 형태 이중 인코딩). */
function symbolSvg(grade: Grade, size: number): string {
  const color = GRADE_COLOR[grade];
  const shape =
    GRADE_SYMBOL[grade] === "circle"
      ? `<circle cx="14" cy="14" r="9" />`
      : GRADE_SYMBOL[grade] === "triangle"
        ? `<path d="M14 4 L23 21 L5 21 Z" />`
        : `<rect x="5" y="5" width="18" height="18" rx="3" />`;
  return `<svg viewBox="0 0 28 28" width="${size}" height="${size}" aria-hidden="true" focusable="false">
    <g fill="${color}" stroke="#ffffff" stroke-width="2" stroke-linejoin="round">${shape}</g>
  </svg>`;
}

/** 접근 가능한 divIcon 마커: 형태 + 흰 외곽 + aria-label. */
function markerIcon(spot: SpotOverview, isSelected: boolean): ReturnType<typeof divIcon> {
  const size = isSelected ? 34 : 26;
  const label =
    `${spot.name} — ${GRADE_KO[spot.grade]}` +
    (spot.has_missing_critical ? ", 정보없음" : "") +
    (isSelected ? ", 선택됨" : "");
  return divIcon({
    className: `map-marker${isSelected ? " is-selected" : ""}`,
    html: `<span class="map-marker-inner" role="img" data-spot-id="${spot.id}" aria-label="${label.replace(
      /"/g,
      "&quot;",
    )}">${symbolSvg(spot.grade, size)}</span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

/** 지도 뷰 (AC7) — 지점을 등급별 색+형태 마커로. 클릭/키보드 → 선택. */
export function SpotMap({
  spots,
  selected,
  onSelect,
}: {
  spots: SpotOverview[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const reducedMotion = usePrefersReducedMotion();
  const icons = useMemo(
    () =>
      new Map(
        spots.map((s) => [`${s.id}:${s.id === selected}`, markerIcon(s, s.id === selected)]),
      ),
    [spots, selected],
  );

  // Leaflet 기본 키보드 핸들러가 divIcon 마커에 걸리지 않으므로, 포커스된
  // 마커의 data-spot-id를 읽어 Enter/Space로 선택한다 (키보드 접근성).
  const onKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const active = document.activeElement;
    const id = active?.querySelector<HTMLElement>("[data-spot-id]")?.dataset.spotId;
    if (id) {
      e.preventDefault();
      onSelect(id);
    }
  };

  if (spots.length === 0) {
    return (
      <div className="map map-empty" role="status">
        표시할 지점이 없습니다.
      </div>
    );
  }

  return (
    <div className="map-wrap" role="group" aria-label="부산 연안 지점 지도" onKeyDown={onKeyDown}>
      <MapContainer
        center={BUSAN_CENTER}
        zoom={11}
        className="map"
        scrollWheelZoom
        zoomAnimation={!reducedMotion}
        fadeAnimation={!reducedMotion}
        markerZoomAnimation={!reducedMotion}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {spots.map((s) => (
          <Marker
            key={s.id}
            position={[s.lat, s.lng]}
            icon={icons.get(`${s.id}:${s.id === selected}`)}
            keyboard
            eventHandlers={{ click: () => onSelect(s.id) }}
          >
            <Tooltip>
              {s.name} — {GRADE_KO[s.grade]}
              {s.has_missing_critical && " (정보없음)"}
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>

      <div className="map-legend" aria-hidden="true">
        {(["SAFE", "CAUTION", "DANGER"] as const).map((g) => (
          <span key={g} className="map-legend-item">
            <span
              className="map-legend-symbol"
              dangerouslySetInnerHTML={{ __html: symbolSvg(g, 16) }}
            />
            {GRADE_KO[g]}
          </span>
        ))}
        <span className="map-legend-item map-legend-missing">□ 정보없음</span>
      </div>
    </div>
  );
}
