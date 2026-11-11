/**
 * WGS-84 与 GCJ-02 之间的坐标换算。
 *
 * 资料库只保存 WGS-84（设备定位、照片 EXIF 都是这套坐标系）；高德瓦片使用
 * GCJ-02。两者的差值在中国境内大约有 300–500 米，直接把 WGS-84 的图钉画到
 * 高德底图上会整体偏移，而且“看起来是对的”，所以显示与交互两头都必须换算。
 *
 * 这里的常数与算法与 backend/app/map_service.py 的 wgs84_to_gcj02 /
 * gcj02_to_wgs84 完全一致：前后端必须用同一套公式，否则同一处地点在表单里
 * 选中的坐标和地图上看到的位置会对不上。
 */

export type CoordinateSystem = "wgs84" | "gcj02";

/** GCJ-02 偏移算法生效的大致范围，与后端 _outside_china 的判断一致。 */
const CHINA_MIN_LATITUDE = 0.8293;
const CHINA_MAX_LATITUDE = 55.8271;
const CHINA_MIN_LONGITUDE = 72.004;
const CHINA_MAX_LONGITUDE = 137.8347;

const PI = Math.PI;

export function outsideChina(latitude: number, longitude: number): boolean {
  return !(
    latitude >= CHINA_MIN_LATITUDE
    && latitude <= CHINA_MAX_LATITUDE
    && longitude >= CHINA_MIN_LONGITUDE
    && longitude <= CHINA_MAX_LONGITUDE
  );
}

function latitudeOffset(x: number, y: number): number {
  let result = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y;
  result += 0.2 * Math.sqrt(Math.abs(x));
  result += ((20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2) / 3;
  result += ((20 * Math.sin(y * PI) + 40 * Math.sin((y / 3) * PI)) * 2) / 3;
  return result + ((160 * Math.sin((y / 12) * PI) + 320 * Math.sin((y / 30) * PI)) * 2) / 3;
}

function longitudeOffset(x: number, y: number): number {
  let result = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y;
  result += 0.1 * Math.sqrt(Math.abs(x));
  result += ((20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2) / 3;
  result += ((20 * Math.sin(x * PI) + 40 * Math.sin((x / 3) * PI)) * 2) / 3;
  return result + ((150 * Math.sin((x / 12) * PI) + 300 * Math.sin((x / 30) * PI)) * 2) / 3;
}

/** 返回 [纬度, 经度]，与 Leaflet 的 [lat, lng] 顺序一致。 */
export function wgs84ToGcj02(latitude: number, longitude: number): [number, number] {
  if (outsideChina(latitude, longitude)) return [latitude, longitude];
  let deltaLatitude = latitudeOffset(longitude - 105, latitude - 35);
  let deltaLongitude = longitudeOffset(longitude - 105, latitude - 35);
  const radLatitude = (latitude / 180) * PI;
  const magic = 1 - 0.006693421622965943 * Math.sin(radLatitude) ** 2;
  const sqrtMagic = Math.sqrt(magic);
  deltaLatitude = (deltaLatitude * 180) / ((6335552.717000426 / (magic * sqrtMagic)) * PI);
  deltaLongitude = (deltaLongitude * 180) / ((6378245 / sqrtMagic) * Math.cos(radLatitude) * PI);
  return [latitude + deltaLatitude, longitude + deltaLongitude];
}

/** 返回 [纬度, 经度]，与 Leaflet 的 [lat, lng] 顺序一致。 */
export function gcj02ToWgs84(latitude: number, longitude: number): [number, number] {
  if (outsideChina(latitude, longitude)) return [latitude, longitude];
  const [convertedLatitude, convertedLongitude] = wgs84ToGcj02(latitude, longitude);
  return [latitude * 2 - convertedLatitude, longitude * 2 - convertedLongitude];
}

/** 把资料库里的 WGS-84 坐标换算成当前底图坐标系，供渲染使用。 */
export function toDisplay(
  latitude: number,
  longitude: number,
  system: CoordinateSystem,
): [number, number] {
  return system === "gcj02" ? wgs84ToGcj02(latitude, longitude) : [latitude, longitude];
}

/** 把底图上取到的坐标换算回 WGS-84，保证写进资料库的永远是 WGS-84。 */
export function toWgs84(
  latitude: number,
  longitude: number,
  system: CoordinateSystem,
): [number, number] {
  return system === "gcj02" ? gcj02ToWgs84(latitude, longitude) : [latitude, longitude];
}
