"""국립해양조사원 해양관측부이 최신 관측데이터 클라이언트.

공공데이터포털의 ``1192136/twRecent`` 서비스를 사용한다. 실제 응답(2026-07-11 검증)의
공식 필드명을 우선하며, 실패하거나 유효한 관측값이 없으면 호출측이 결측 처리할 수 있도록
``None``을 반환한다.

실측 확인된 공식 필드(부이 최신 관측):
  wvhgt=파고(m), wspd=풍속(m/s), crsp=유속(cm/s), wtem=수온(°C),
  wndrct=풍향, crdir=유향, wvpd=파주기, artmp=기온, atmpr=기압, slnty=염분.
응답 래퍼는 ``{header, body:{items:{item:[...]}}}`` 로 ``response`` 상위 래퍼가 없다.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from ..models import Metric
from ..spots import Spot
from .base import fetch_json

KHOA_URL = "https://apis.data.go.kr/1192136/twRecent/GetTWRecentApiService"

# 실측 확정 공식 필드명을 앞에 두고, 게이트웨이 표기 변형을 뒤에 폴백으로 둔다.
FIELD_ALIASES: dict[Metric, tuple[str, ...]] = {
    Metric.WAVE_HEIGHT: ("wvhgt", "waveHeight", "wave_height", "obs_wave_height", "obs_wh"),
    Metric.CURRENT_SPEED: ("crsp", "currentSpeed", "current_speed", "obs_current_speed", "obs_cs"),
    Metric.WATER_TEMP: ("wtem", "waterTemp", "waterTemperature", "water_temp", "obs_wtemp"),
    Metric.WIND_SPEED: ("wspd", "windSpeed", "wind_speed", "obs_wind_speed", "obs_ws"),
}

# 원 단위 → 엔진 표준 단위 변환. KHOA 유속(crsp)은 cm/s → m/s.
_CONVERT: dict[Metric, Callable[[float], float]] = {
    Metric.CURRENT_SPEED: lambda v: round(v / 100.0, 3),
}


async def fetch_spot(spot: Spot, api_key: str) -> dict[Metric, float] | None:
    """지점의 최신 해양관측부이 값을 조회한다."""
    if not api_key or not spot.khoa_obs_code or spot.khoa_obs_code.startswith("TBD_"):
        return None

    raw = await fetch_json(
        KHOA_URL,
        params={
            "serviceKey": api_key,
            "pageNo": 1,
            "numOfRows": 300,
            "type": "json",
            "obsCode": spot.khoa_obs_code,
            "reqDate": date.today().strftime("%Y%m%d"),
            "min": 60,
        },
    )
    return _parse(raw) if raw is not None else None


def _parse(raw: Any) -> dict[Metric, float] | None:
    """공공데이터포털 JSON 래퍼에서 가장 최신의 유효 레코드를 읽는다."""
    records = _records(raw)
    for record in reversed(records):
        out: dict[Metric, float] = {}
        for metric, aliases in FIELD_ALIASES.items():
            value = _first(record, aliases)
            if value is None:
                continue
            try:
                num = float(value)
            except (TypeError, ValueError):
                continue
            convert = _CONVERT.get(metric)
            out[metric] = convert(num) if convert else num
        if out:
            return out
    return None


def _records(raw: Any) -> list[dict[str, Any]]:
    """response 래퍼 유무와 무관하게 item 리스트를 찾아낸다."""
    if not isinstance(raw, dict):
        return []

    # body 는 top-level(twRecent 실측) 또는 response 하위에 올 수 있다.
    bodies: list[Any] = [raw.get("body")]
    response = raw.get("response")
    if isinstance(response, dict):
        bodies.append(response.get("body"))

    for body in bodies:
        if isinstance(body, dict):
            items = body.get("items")
            if isinstance(items, dict):
                item = items.get("item")
                if isinstance(item, list):
                    return [entry for entry in item if isinstance(entry, dict)]
                if isinstance(item, dict):
                    return [item]
            for key in ("items", "data"):
                node = body.get(key)
                if isinstance(node, list):
                    return [entry for entry in node if isinstance(entry, dict)]

    # 단순화된 래퍼(result.data / data / items) 폴백
    result = raw.get("result")
    fallbacks: list[Any] = [raw.get("data"), raw.get("items")]
    if isinstance(result, dict):
        fallbacks.extend((result.get("data"), result.get("items")))
    for node in fallbacks:
        if isinstance(node, list):
            return [entry for entry in node if isinstance(entry, dict)]
    return []


def _first(record: dict[str, Any], aliases: tuple[str, ...]) -> Any | None:
    for name in aliases:
        value = record.get(name)
        if value not in (None, "", "-"):
            return value
    return None
