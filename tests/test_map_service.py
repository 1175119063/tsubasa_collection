from urllib.parse import parse_qs, urlsplit

from backend.app.map_service import TiandituService, gcj02_to_wgs84, wgs84_to_gcj02


def test_coordinate_conversion_round_trip_is_precise_enough_for_map_picker():
    latitude, longitude = 36.6, 117.06
    gcj_latitude, gcj_longitude = wgs84_to_gcj02(latitude, longitude)
    restored_latitude, restored_longitude = gcj02_to_wgs84(
        gcj_latitude, gcj_longitude
    )

    assert abs(restored_latitude - latitude) < 0.00002
    assert abs(restored_longitude - longitude) < 0.00002


def test_coordinate_conversion_does_not_shift_points_outside_china():
    assert wgs84_to_gcj02(51.5074, -0.1278) == (51.5074, -0.1278)
    assert gcj02_to_wgs84(51.5074, -0.1278) == (51.5074, -0.1278)


def test_tianditu_connection_uses_official_wmts_with_key(monkeypatch):
    requested: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _size: int) -> bytes:
            return b"\x89PNG\r\n\x1a\nvalid-tile"

    def fake_urlopen(request, timeout):
        requested["url"] = request.full_url
        requested["timeout"] = timeout
        return Response()

    monkeypatch.setattr("backend.app.map_service.urlopen", fake_urlopen)
    TiandituService("browser-key-1234").test_connection()

    parsed = urlsplit(str(requested["url"]))
    query = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.hostname == "t0.tianditu.gov.cn"
    assert query["LAYER"] == ["vec"]
    assert query["TILEMATRIXSET"] == ["w"]
    assert query["tk"] == ["browser-key-1234"]
    assert requested["timeout"] == 8
