import json

from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from test_demo_flow import jpeg_bytes, observation_payload


def test_create_manage_and_delete_multiple_observation_photos(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        payload = observation_payload()
        payload["photos"] = [
            {
                "observed_at": "2026-08-15T08:30",
                "includes_primary": True,
                "species_ids": [],
                "is_cover": False,
            },
            {
                "observed_at": "2026-08-15T08:32",
                "includes_primary": True,
                "species_ids": [],
                "is_cover": True,
            },
        ]
        response = client.post(
            "/api/observations",
            data={"payload": json.dumps(payload, ensure_ascii=False)},
            files=[
                ("photo", ("first.jpg", jpeg_bytes((10, 20, 30)), "image/jpeg")),
                (
                    "additional_photos",
                    ("second.jpg", jpeg_bytes((40, 50, 60)), "image/jpeg"),
                ),
            ],
        )
        assert response.status_code == 201, response.text
        observation_id = response.json()["observation_id"]
        record = client.get("/api/observations").json()[0]
        assert record["photo_count"] == 2
        assert [photo["observed_at"] for photo in record["photos"]] == [
            "2026-08-15T08:30",
            "2026-08-15T08:32",
        ]
        assert record["photos"][1]["is_cover"] is True
        assert record["photo_asset_id"] == record["photos"][1]["asset_id"]
        assert record["observed_at"] == "2026-08-15T08:30"
        entry_id = record["species_entries"][0]["id"]

        added = client.post(
            f"/api/observations/{observation_id}/photos",
            data={
                "payload": json.dumps(
                    {
                        "observed_at": "2026-08-15T08:35",
                        "species_entry_ids": [entry_id],
                        "is_cover": False,
                    }
                )
            },
            files={
                "photo": ("third.jpg", jpeg_bytes((70, 80, 90)), "image/jpeg")
            },
        )
        assert added.status_code == 201, added.text
        assert added.json()["photo_count"] == 3
        third = added.json()["photos"][2]

        covered = client.patch(
            f"/api/observations/{observation_id}/photos/{third['id']}",
            json={
                "observed_at": "2026-08-15T08:36",
                "species_entry_ids": [entry_id],
                "is_cover": True,
            },
        )
        assert covered.status_code == 200, covered.text
        assert covered.json()["photo_asset_id"] == third["asset_id"]
        assert covered.json()["observed_at"] == "2026-08-15T08:30"

        removed = client.delete(
            f"/api/observations/{observation_id}/photos/{third['id']}"
        )
        assert removed.status_code == 200, removed.text
        assert removed.json()["photo_count"] == 2
        assert sum(photo["is_cover"] for photo in removed.json()["photos"]) == 1

        remaining = removed.json()["photos"]
        assert client.delete(
            f"/api/observations/{observation_id}/photos/{remaining[1]['id']}"
        ).status_code == 200
        cannot_delete_last = client.delete(
            f"/api/observations/{observation_id}/photos/{remaining[0]['id']}"
        )
        assert cannot_delete_last.status_code == 422


def test_photo_requires_an_observation_species_and_rejects_duplicates(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        payload = observation_payload()
        created = client.post(
            "/api/observations",
            data={"payload": json.dumps(payload, ensure_ascii=False)},
            files={"photo": ("bird.jpg", jpeg_bytes(), "image/jpeg")},
        ).json()
        photo = jpeg_bytes((90, 80, 70))
        invalid = client.post(
            f"/api/observations/{created['observation_id']}/photos",
            data={
                "payload": json.dumps(
                    {
                        "observed_at": "2026-08-15T08:40",
                        "species_entry_ids": [],
                        "is_cover": False,
                    }
                )
            },
            files={"photo": ("extra.jpg", photo, "image/jpeg")},
        )
        assert invalid.status_code == 422

        entry_id = created["species_entries"][0]["id"]
        for expected in (201, 409):
            response = client.post(
                f"/api/observations/{created['observation_id']}/photos",
                data={
                    "payload": json.dumps(
                        {
                            "observed_at": "2026-08-15T08:40",
                            "species_entry_ids": [entry_id],
                            "is_cover": False,
                        }
                    )
                },
                files={"photo": ("extra.jpg", photo, "image/jpeg")},
            )
            assert response.status_code == expected, response.text


def test_species_proof_uses_a_photo_linked_to_that_species(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        first = client.post(
            "/api/observations",
            data={"payload": json.dumps(observation_payload(), ensure_ascii=False)},
            files={"photo": ("first-species.jpg", jpeg_bytes(), "image/jpeg")},
        ).json()
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
        second_payload["observed_at"] = "2026-08-15T09:00"
        second = client.post(
            "/api/observations",
            data={"payload": json.dumps(second_payload, ensure_ascii=False)},
            files={"photo": ("second-species.jpg", jpeg_bytes((80, 70, 60)), "image/jpeg")},
        ).json()

        payload = observation_payload()
        payload["species_id"] = first["species_id"]
        payload["new_species"] = None
        payload["observed_at"] = "2026-08-16T08:30"
        payload["additional_species"] = [
            {
                "species_id": second["species_id"],
                "photo_type": "individual",
                "sex": "unknown",
                "life_stage": "unknown",
                "subspecies_id": None,
                "notes": None,
            }
        ]
        payload["photos"] = [
            {
                "observed_at": "2026-08-16T08:30",
                "includes_primary": True,
                "species_ids": [],
                "is_cover": True,
            },
            {
                "observed_at": "2026-08-16T08:31",
                "includes_primary": False,
                "species_ids": [second["species_id"]],
                "is_cover": False,
            },
        ]
        created = client.post(
            "/api/observations",
            data={"payload": json.dumps(payload, ensure_ascii=False)},
            files=[
                ("photo", ("primary-only.jpg", jpeg_bytes((30, 40, 50)), "image/jpeg")),
                (
                    "additional_photos",
                    ("sparrow-only.jpg", jpeg_bytes((100, 110, 120)), "image/jpeg"),
                ),
            ],
        )
        assert created.status_code == 201, created.text
        observation_id = created.json()["observation_id"]
        record = next(
            item for item in client.get("/api/observations").json()
            if item["id"] == observation_id
        )
        primary_entry = next(item for item in record["species_entries"] if item["is_primary"])
        secondary_entry = next(item for item in record["species_entries"] if not item["is_primary"])
        assert record["photos"][0]["species_entry_ids"] == [primary_entry["id"]]
        assert record["photos"][1]["species_entry_ids"] == [secondary_entry["id"]]

        selected = client.put(
            f"/api/species/{second['species_id']}/cover",
            json={"observation_id": observation_id},
        )
        assert selected.status_code == 200, selected.text
        assert selected.json()["cover_asset_id"] == record["photos"][1]["asset_id"]
        detail = client.get(f"/api/species/{second['species_id']}").json()
        assert detail["cover"]["asset_id"] == record["photos"][1]["asset_id"]
