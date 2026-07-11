import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { SpotOverview } from "../types";
import { GRADE_COLOR, GRADE_KO } from "../types";

const BUSAN_CENTER: [number, number] = [35.12, 129.08];

/** 지도 뷰 (AC7) — 지점을 등급 색 원마커로. 클릭 → 선택. */
export function SpotMap({
  spots,
  selected,
  onSelect,
}: {
  spots: SpotOverview[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <MapContainer center={BUSAN_CENTER} zoom={11} className="map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; OpenStreetMap'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {spots.map((s) => (
        <CircleMarker
          key={s.id}
          center={[s.lat, s.lng]}
          radius={s.id === selected ? 13 : 9}
          pathOptions={{
            color: s.id === selected ? "#fff" : GRADE_COLOR[s.grade],
            weight: s.id === selected ? 3 : 1.5,
            fillColor: GRADE_COLOR[s.grade],
            fillOpacity: 0.85,
          }}
          eventHandlers={{ click: () => onSelect(s.id) }}
        >
          <Tooltip>
            {s.name} — {GRADE_KO[s.grade]}
            {s.has_missing_critical && " (정보없음)"}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
