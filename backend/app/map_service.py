import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class MapServiceError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _outside_china(latitude: float, longitude: float) -> bool:
    return not (0.8293 <= latitude <= 55.8271 and 72.004 <= longitude <= 137.8347)


def _latitude_offset(x: float, y: float) -> float:
    result = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y
    result += 0.2 * math.sqrt(abs(x))
    result += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    result += (20 * math.sin(y * math.pi) + 40 * math.sin(y / 3 * math.pi)) * 2 / 3
    return result + (160 * math.sin(y / 12 * math.pi) + 320 * math.sin(y / 30 * math.pi)) * 2 / 3


def _longitude_offset(x: float, y: float) -> float:
    result = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y
    result += 0.1 * math.sqrt(abs(x))
    result += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    result += (20 * math.sin(x * math.pi) + 40 * math.sin(x / 3 * math.pi)) * 2 / 3
    return result + (150 * math.sin(x / 12 * math.pi) + 300 * math.sin(x / 30 * math.pi)) * 2 / 3


def wgs84_to_gcj02(latitude: float, longitude: float) -> tuple[float, float]:
    if _outside_china(latitude, longitude):
        return latitude, longitude
    delta_lat = _latitude_offset(longitude - 105, latitude - 35)
    delta_lng = _longitude_offset(longitude - 105, latitude - 35)
    rad_lat = latitude / 180 * math.pi
    magic = 1 - 0.006693421622965943 * math.sin(rad_lat) ** 2
    sqrt_magic = math.sqrt(magic)
    delta_lat = delta_lat * 180 / ((6335552.717000426 / (magic * sqrt_magic)) * math.pi)
    delta_lng = delta_lng * 180 / ((6378245 / sqrt_magic) * math.cos(rad_lat) * math.pi)
    return latitude + delta_lat, longitude + delta_lng


def gcj02_to_wgs84(latitude: float, longitude: float) -> tuple[float, float]:
    if _outside_china(latitude, longitude):
        return latitude, longitude
    converted_lat, converted_lng = wgs84_to_gcj02(latitude, longitude)
    return latitude * 2 - converted_lat, longitude * 2 - converted_lng


class AmapService:
    base_url = "https://restapi.amap.com/v3"

    def __init__(self, key: str | None) -> None:
        self.key = (key or "").strip()
        if not self.key:
            raise MapServiceError("尚未配置高德 Web 服务 Key。", 503)

    def _get(self, path: str, parameters: dict[str, str]) -> dict:
        url = f"{self.base_url}/{path}?{urlencode({**parameters, 'key': self.key})}"
        request = Request(url, headers={"User-Agent": "Tsubasa-Field-Journal/0.2"})
        try:
            with urlopen(request, timeout=8) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MapServiceError("高德地图服务暂时无法访问，请稍后重试。") from exc
        if payload.get("status") != "1":
            info = payload.get("info") or "未知错误"
            if info in {"USERKEY_PLAT_NOMATCH", "INVALID_USER_KEY"}:
                raise MapServiceError(
                    "当前 Key 不是可用的高德 Web 服务 Key，"
                    "请在控制台新建 Web 服务类型 Key。",
                    503,
                )
            raise MapServiceError(f"高德地图查询失败：{info}")
        return payload

    def search(self, query: str, city: str | None = None) -> list[dict]:
        parameters = {"keywords": query, "offset": "8", "page": "1", "extensions": "base"}
        if city:
            parameters["city"] = city
        payload = self._get("place/text", parameters)
        results = []
        for poi in payload.get("pois", []):
            try:
                longitude, latitude = map(float, poi["location"].split(","))
            except (KeyError, TypeError, ValueError):
                continue
            wgs_latitude, wgs_longitude = gcj02_to_wgs84(latitude, longitude)
            results.append(
                {
                    "id": poi.get("id"),
                    "name": poi.get("name"),
                    "address": poi.get("address") if isinstance(poi.get("address"), str) else None,
                    "province": poi.get("pname"),
                    "city": poi.get("cityname") if isinstance(poi.get("cityname"), str) else None,
                    "district": poi.get("adname"),
                    "adcode": poi.get("adcode"),
                    "latitude": round(wgs_latitude, 7),
                    "longitude": round(wgs_longitude, 7),
                }
            )
        return results

    def reverse_wgs84(self, latitude: float, longitude: float) -> dict:
        gcj_latitude, gcj_longitude = wgs84_to_gcj02(latitude, longitude)
        payload = self._get(
            "geocode/regeo",
            {"location": f"{gcj_longitude},{gcj_latitude}", "extensions": "base", "radius": "800"},
        )
        regeocode = payload.get("regeocode") or {}
        component = regeocode.get("addressComponent") or {}
        return {
            "formatted_address": regeocode.get("formatted_address"),
            "province": component.get("province"),
            "city": component.get("city") if isinstance(component.get("city"), str) else None,
            "district": component.get("district"),
            "adcode": component.get("adcode"),
        }
