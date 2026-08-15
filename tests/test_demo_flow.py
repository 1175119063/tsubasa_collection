import io
import json

from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from PIL import Image


def jpeg_bytes(
    color: tuple[int, int, int] = (73, 105, 82),
    exif_datetime: str | None = None,
) -> bytes:
    buffer = io.BytesIO()
    exif = Image.Exif()
    if exif_datetime:
        exif[36867] = exif_datetime
    Image.new("RGB", (800, 600), color).save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def observation_payload(scientific_name: str = "Lonchura striata") -> dict:
    return {
        "species_id": None,
        "new_species": {
            "order": {"chinese_name": "雀形目", "scientific_name": "Passeriformes"},
            "family": {"chinese_name": "梅花雀科", "scientific_name": "Estrildidae"},
            "genus": {"chinese_name": "文鸟属", "scientific_name": "Lonchura"},
            "chinese_name": "白腰文鸟",
            "scientific_name": scientific_name,
            "iucn_status": "LC",
            "china_protection_status": "three_protected",
            "has_subspecies": False,
            "subspecies": [],
            "notes": None,
        },
        "subspecies_id": None,
        "subspecies_scientific_name": None,
        "photo_type": "individual",
        "observed_at": "2026-08-15T08:30",
        "latitude": 30.2741,
        "longitude": 120.1551,
        "country_code": "CN",
        "country_name": "中国",
        "admin1_code": "CN-ZJ",
        "admin1_name": "浙江省",
        "locality": "杭州西湖",
        "season": "summer",
        "season_note": None,
        "sex": "male",
        "life_stage": "adult",
        "notes": "第一笔测试观察",
    }


def post_observation(client: TestClient, payload: dict, color=(73, 105, 82)):
    return client.post(
        "/api/observations",
        data={"payload": json.dumps(payload, ensure_ascii=False)},
        files={"photo": ("bird.jpg", jpeg_bytes(color), "image/jpeg")},
    )


def location_payload(name: str = "杭州西湖") -> dict:
    return {
        "name": name,
        "location_type": "urban_park",
        "country_code": "CN",
        "country_name": "中国",
        "admin1_code": "CN-ZJ",
        "admin1_name": "浙江省",
        "city": "杭州市",
        "district": "西湖区",
        "center_latitude": 30.2741,
        "center_longitude": 120.1551,
        "radius_meters": 3000,
        "notes": "测试地点",
        "link_matching_records": True,
    }


def test_complete_demo_flow_and_species_id_is_never_reused(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        observations_page = client.get("/observations")
        dex_page = client.get("/dex")
        locations_page = client.get("/locations")
        trips_page = client.get("/trips")
        assert observations_page.status_code == 200
        assert dex_page.status_code == 200
        assert locations_page.status_code == 200
        assert trips_page.status_code == 200
        assert 'href="/locations"' in client.get("/").text
        assert "观鸟行程" in client.get("/").text
        assert 'href="/trips"' in client.get("/").text
        assert 'id="new-location-button"' in locations_page.text
        assert 'id="location-grid"' in locations_page.text
        assert 'id="trip-groups"' in trips_page.text
        assert 'id="trip-location-filter"' in trips_page.text
        assert 'id="observation-groups"' in observations_page.text
        assert 'id="observation-detail-dialog"' in observations_page.text
        assert 'id="observation-year-filter"' in observations_page.text
        assert 'id="species-grid"' in dex_page.text
        assert 'id="family-filter"' in dex_page.text
        assert 'id="genus-filter"' in dex_page.text
        assert 'id="species-filter"' in dex_page.text
        assert "/observations?observation=" in client.get("/static/dex.js").text
        observations_script = client.get("/static/observations.js").text
        assert 'data-edit-observation="${item.id}"' in observations_script
        assert 'method: "PATCH"' in observations_script
        assert client.get("/api/health").json()["status"] == "ok"

        created = post_observation(client, observation_payload())
        assert created.status_code == 201, created.text
        first = created.json()
        assert first["catalog_number"] == "AV-000001"

        species_list = client.get("/api/species").json()
        assert len(species_list) == 1
        assert species_list[0]["observation_count"] == 1
        assert species_list[0]["family_scientific_name"] == "Estrildidae"
        assert species_list[0]["genus_scientific_name"] == "Lonchura"

        observations = client.get("/api/observations").json()
        assert observations[0]["species_scientific_name"] == "Lonchura striata"
        assert observations[0]["catalog_number"] == "AV-000001"

        taxonomy = client.get("/api/taxonomy/tree").json()
        assert taxonomy[0]["scientific_name"] == "Passeriformes"
        assert taxonomy[0]["families"][0]["scientific_name"] == "Estrildidae"
        assert taxonomy[0]["families"][0]["genera"][0]["scientific_name"] == "Lonchura"

        detail_response = client.get(f"/api/species/{first['species_id']}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["chinese_name"] == "白腰文鸟"
        assert detail["first_encounter"]["locality"] == "杭州西湖"
        assert detail["collected"]["seasons"][0]["value"] == "summer"
        assert detail["collected"]["sexes"][0]["value"] == "male"
        assert detail["collected"]["life_stages"][0]["value"] == "adult"

        media_response = client.get(detail["cover_url"])
        assert media_response.status_code == 200
        assert media_response.headers["content-type"].startswith("image/jpeg")

        observation_id = first["observation_id"]
        deleted = client.delete(f"/api/observations/{observation_id}")
        assert deleted.status_code == 200
        assert deleted.json()["removed_species"] is True
        assert client.get("/api/species").json() == []

        recreated = post_observation(
            client,
            observation_payload(scientific_name="Lonchura striata"),
            color=(92, 86, 67),
        )
        assert recreated.status_code == 201, recreated.text
        assert recreated.json()["catalog_number"] == "AV-000002"


def test_group_photo_rejects_individual_attributes(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    payload = observation_payload()
    payload["photo_type"] = "group"

    with TestClient(app) as client:
        response = post_observation(client, payload)

    assert response.status_code == 422
    assert "群体照片不能填写" in response.text


def test_non_jpeg_upload_is_rejected_without_empty_species(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        response = client.post(
            "/api/observations",
            data={"payload": json.dumps(observation_payload(), ensure_ascii=False)},
            files={"photo": ("bird.jpg", b"not-a-jpeg", "image/jpeg")},
        )
        assert response.status_code == 422
        assert client.get("/api/species").json() == []


def test_new_species_reuses_existing_taxonomy_path(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        first = post_observation(client, observation_payload())
        assert first.status_code == 201

        second_payload = observation_payload("Lonchura punctulata")
        second_payload["new_species"]["chinese_name"] = "斑文鸟"
        second = post_observation(client, second_payload, color=(121, 105, 77))
        assert second.status_code == 201, second.text

        taxonomy = client.get("/api/taxonomy/tree").json()
        assert len(taxonomy) == 1
        assert len(taxonomy[0]["families"]) == 1
        assert len(taxonomy[0]["families"][0]["genera"]) == 1
        assert len(client.get("/api/species").json()) == 2


def test_existing_family_cannot_be_attached_to_another_order(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        first = post_observation(client, observation_payload())
        assert first.status_code == 201

        invalid = observation_payload("Calonectris leucomelas")
        invalid["new_species"]["chinese_name"] = "白额鹱"
        invalid["new_species"]["order"] = {
            "chinese_name": "鹱形目",
            "scientific_name": "Procellariiformes",
        }
        response = post_observation(client, invalid, color=(95, 100, 105))
        assert response.status_code == 409
        assert "已属于其他目" in response.text


def test_exif_datetime_original_is_returned_to_the_minute(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        response = client.post(
            "/api/media/exif-time",
            files={
                "photo": (
                    "bird.jpg",
                    jpeg_bytes(exif_datetime="2026:08:13 16:29:45"),
                    "image/jpeg",
                )
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "observed_at": "2026-08-13T16:29",
        "source": "DateTimeOriginal",
    }


def test_species_cover_can_use_a_later_observation(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        first = post_observation(client, observation_payload())
        assert first.status_code == 201

        second_payload = observation_payload()
        second_payload["species_id"] = first.json()["species_id"]
        second_payload["new_species"] = None
        second_payload["observed_at"] = "2026-08-16T09:10"
        second = post_observation(client, second_payload, color=(120, 90, 65))
        assert second.status_code == 201

        response = client.put(
            f"/api/species/{first.json()['species_id']}/cover",
            json={"observation_id": second.json()["observation_id"]},
        )
        assert response.status_code == 200
        assert response.json()["cover_observation_id"] == second.json()["observation_id"]

        detail = client.get(f"/api/species/{first.json()['species_id']}").json()
        assert detail["cover"]["observation_id"] == second.json()["observation_id"]


def test_observation_update_is_limited_to_individual_fields_and_notes(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        created = post_observation(client, observation_payload())
        observation_id = created.json()["observation_id"]

        response = client.patch(
            f"/api/observations/{observation_id}",
            json={
                "sex": "female",
                "life_stage": "subadult",
                "subspecies_id": None,
                "notes": "修改后的备注",
            },
        )
        assert response.status_code == 200
        assert response.json()["species_id"] == created.json()["species_id"]
        assert response.json()["sex"] == "female"
        assert response.json()["life_stage"] == "subadult"
        assert response.json()["notes"] == "修改后的备注"

        forbidden = client.patch(
            f"/api/observations/{observation_id}",
            json={
                "species_id": 999,
                "sex": "male",
                "life_stage": "adult",
                "subspecies_id": None,
                "notes": None,
            },
        )
        assert forbidden.status_code == 422


def test_group_observation_update_only_allows_notes(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    payload = observation_payload()
    payload.update({"photo_type": "group", "sex": None, "life_stage": None})
    with TestClient(app) as client:
        created = post_observation(client, payload)
        observation_id = created.json()["observation_id"]

        notes_only = client.patch(
            f"/api/observations/{observation_id}",
            json={"sex": None, "life_stage": None, "subspecies_id": None, "notes": "群体备注"},
        )
        assert notes_only.status_code == 200
        assert notes_only.json()["notes"] == "群体备注"

        invalid = client.patch(
            f"/api/observations/{observation_id}",
            json={"sex": "male", "life_stage": "adult", "notes": "不应保存"},
        )
        assert invalid.status_code == 422


def test_observation_update_can_change_to_another_subspecies_of_same_species(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    payload = observation_payload()
    payload["new_species"]["has_subspecies"] = True
    payload["new_species"]["subspecies"] = [
        {"scientific_name": "Lonchura striata swinhoei", "chinese_name": None},
        {"scientific_name": "Lonchura striata acuticauda", "chinese_name": None},
    ]
    payload["subspecies_scientific_name"] = "Lonchura striata swinhoei"

    with TestClient(app) as client:
        created = post_observation(client, payload)
        species_id = created.json()["species_id"]
        detail = client.get(f"/api/species/{species_id}").json()
        target = next(
            item
            for item in detail["subspecies"]
            if item["scientific_name"] == "Lonchura striata acuticauda"
        )

        response = client.patch(
            f"/api/observations/{created.json()['observation_id']}",
            json={
                "sex": "male",
                "life_stage": "adult",
                "subspecies_id": target["id"],
                "notes": None,
            },
        )
        assert response.status_code == 200
        assert response.json()["subspecies"]["id"] == target["id"]


def test_location_auto_links_matching_records_and_delete_only_unlinks(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        first = post_observation(client, observation_payload())
        second_payload = observation_payload()
        second_payload["species_id"] = first.json()["species_id"]
        second_payload["new_species"] = None
        second_payload["observed_at"] = "2026-08-15T10:30"
        second = post_observation(client, second_payload, color=(90, 110, 70))
        assert second.status_code == 201

        created = client.post(
            "/api/locations",
            json=location_payload(),
        )
        assert created.status_code == 201, created.text
        location = created.json()
        assert location["catalog_number"] == "LOC-000001"
        assert location["observation_count"] == 2
        assert location["species_count"] == 1
        assert location["visit_day_count"] == 1
        assert location["monthly_activity"][0]["visit_day_count"] == 1

        cover_response = client.post(
            f"/api/locations/{location['id']}/cover",
            files={"photo": ("place.jpg", jpeg_bytes((180, 50, 50)), "image/jpeg")},
        )
        assert cover_response.status_code == 200, cover_response.text
        assert cover_response.json()["cover_source"] == "custom"
        custom_cover_url = cover_response.json()["cover_url"]
        assert client.get(custom_cover_url).status_code == 200

        observations = client.get("/api/observations").json()
        assert all(item["location"]["id"] == location["id"] for item in observations)

        deleted = client.delete(f"/api/locations/{location['id']}")
        assert deleted.status_code == 200
        assert deleted.json()["unlinked_observation_count"] == 2
        remaining = client.get("/api/observations").json()
        assert len(remaining) == 2
        assert all(item["location"] is None for item in remaining)
        assert client.get(custom_cover_url).status_code == 404


def test_trip_association_statistics_cover_and_constraints(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        location = client.post("/api/locations", json=location_payload()).json()

        first_payload = observation_payload()
        first_payload["locality"] = "西湖苏堤"
        first_payload["observed_at"] = "2026-08-15T08:30"
        first = post_observation(client, first_payload)

        second_payload = observation_payload("Passer montanus")
        second_payload["new_species"]["family"] = {
            "chinese_name": "麻雀科",
            "scientific_name": "Passeridae",
        }
        second_payload["new_species"]["genus"] = {
            "chinese_name": "麻雀属",
            "scientific_name": "Passer",
        }
        second_payload["new_species"]["chinese_name"] = "树麻雀"
        second_payload["location_id"] = location["id"]
        second_payload["observed_at"] = "2026-08-15T09:45"
        second = post_observation(client, second_payload, color=(115, 95, 70))

        trip = client.post(
            "/api/trips",
            json={
                "location_id": location["id"],
                "started_at": "2026-08-15T08:00",
                "ended_at": "2026-08-15T11:00",
                "notes": "清晨观鸟",
            },
        )
        assert trip.status_code == 201, trip.text
        trip_id = trip.json()["id"]

        linked = client.put(
            f"/api/trips/{trip_id}/observations",
            json={
                "observation_ids": [
                    first.json()["observation_id"],
                    second.json()["observation_id"],
                ]
            },
        )
        assert linked.status_code == 200, linked.text
        detail = linked.json()
        assert detail["observation_count"] == 2
        assert detail["species_count"] == 2
        assert detail["genus_count"] == 2
        assert detail["family_count"] == 2
        assert detail["cover_observation_id"] == first.json()["observation_id"]

        observations = client.get("/api/observations").json()
        first_observation = next(
            item for item in observations if item["id"] == first.json()["observation_id"]
        )
        assert first_observation["location"]["id"] == location["id"]
        assert first_observation["trip"]["id"] == trip_id

        cover = client.put(
            f"/api/trips/{trip_id}/cover",
            json={"observation_id": second.json()["observation_id"]},
        )
        assert cover.status_code == 200
        assert cover.json()["cover_observation_id"] == second.json()["observation_id"]

        invalid_update = client.put(
            f"/api/trips/{trip_id}",
            json={
                "location_id": location["id"],
                "started_at": "2026-08-15T08:00",
                "ended_at": "2026-08-15T09:00",
                "notes": None,
            },
        )
        assert invalid_update.status_code == 422

        other_trip = client.post(
            "/api/trips",
            json={
                "location_id": location["id"],
                "started_at": "2026-08-15T08:00",
                "ended_at": "2026-08-15T11:00",
                "notes": None,
            },
        ).json()
        conflict = client.put(
            f"/api/trips/{other_trip['id']}/observations",
            json={"observation_ids": [first.json()["observation_id"]]},
        )
        assert conflict.status_code == 409

        deleted = client.delete(f"/api/trips/{trip_id}")
        assert deleted.status_code == 200
        assert deleted.json()["unlinked_observation_count"] == 2
        assert all(item["trip"] is None for item in client.get("/api/observations").json())
