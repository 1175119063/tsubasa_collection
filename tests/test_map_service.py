from backend.app.map_service import gcj02_to_wgs84, wgs84_to_gcj02


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
