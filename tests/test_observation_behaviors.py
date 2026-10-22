import csv
import io
import json
import sqlite3

import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(_env_file=None, data_dir=tmp_path / "library"))) as api:
        yield api


def create(client, payload, jpeg_bytes):
    response = client.post(
        "/api/observations", data={"payload": json.dumps(payload)},
        files={"photo": ("bird.jpg", jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def tags(client, species_id):
    response = client.get(f"/api/species/{species_id}/behaviors")
    assert response.status_code == 200, response.text
    return response.json()


def test_behaviors_are_shared_between_observation_and_dossier(
    client, observation_payload, jpeg_bytes,
):
    payload = observation_payload()
    payload["behavior_labels"] = ["飞行", "捕食"]
    first = create(client, payload, jpeg_bytes)
    sid = first["species_id"]
    payload.update(species_id=sid, new_species=None, behavior_labels=["飞行"])
    second = create(client, payload, jpeg_bytes)
    exported = client.get("/api/exports/observations.csv")
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert {row["behavior_labels"] for row in rows} == {"飞行 | 捕食", "飞行"}
    flying, feeding = tags(client, sid)
    assert flying["observation_ids"] == [first["observation_id"], second["observation_id"]]
    assert feeding["observation_ids"] == [first["observation_id"]]
    # Rename and change membership in the dossier; observation fields must reflect both.
    response = client.put(f"/api/species/{sid}/profile", json={"behaviors": [
        {"id": flying["id"], "label": "盘旋", "observation_ids": [second["observation_id"]]},
        {"id": feeding["id"], "label": "捕食", "observation_ids": []},
    ]})
    assert response.status_code == 200, response.text
    records = {item["id"]: item for item in client.get("/api/observations").json()}
    assert records[first["observation_id"]]["behavior_labels"] == []
    assert records[second["observation_id"]]["species_entries"][0]["behavior_labels"] == ["盘旋"]
    assert tags(client, sid)[0]["id"] == flying["id"]
    # Omitting this field does not erase observations' behaviors.
    saved = client.put(f"/api/species/{sid}/profile", json={"introduction": "说明"})
    assert saved.status_code == 200
    assert tags(client, sid)[0]["observation_ids"] == [second["observation_id"]]
    # Unselect in a record: retain the tag, clear its membership.
    response = client.patch(f"/api/observations/{second['observation_id']}", json={
        "sex": "male", "life_stage": "adult", "behavior_labels": [],
    })
    assert response.status_code == 200, response.text
    assert all(not tag["linked"] for tag in tags(client, sid))
    # Deleting a tag removes its associations, never its observations.
    assert client.put(f"/api/species/{sid}/profile", json={"behaviors": []}).status_code == 200
    assert tags(client, sid) == []
    assert len(client.get("/api/observations").json()) == 2


def test_behaviors_are_scoped_to_species_and_cascade_with_entries(
    client, observation_payload, jpeg_bytes,
):
    first = create(client, observation_payload(), jpeg_bytes)
    payload = observation_payload()
    payload["new_species"]["scientific_name"] = "Lonchura punctulata"
    payload["behavior_labels"] = ["飞行"]
    payload["additional_species"] = [{
        "species_id": first["species_id"], "photo_type": "group", "behavior_labels": ["捕食"],
    }]
    mixed = create(client, payload, jpeg_bytes)
    record = next(v for v in client.get("/api/observations").json()
                  if v["id"] == mixed["observation_id"])
    entries = record["species_entries"]
    assert entries[0]["behavior_labels"] == ["飞行"]
    assert entries[1]["behavior_labels"] == ["捕食"]
    # A group can have several behavior labels without individual attributes.
    result = client.patch(
        f"/api/observations/{record['id']}/species/{entries[1]['id']}",
        json={"behavior_labels": ["捕食", "休息"]},
    )
    assert result.status_code == 200, result.text
    tag = tags(client, first["species_id"])[0]
    bad = client.put(f"/api/species/{first['species_id']}/profile", json={"behaviors": [{
        "id": tag["id"], "label": "捕食", "observation_ids": [999999],
    }]})
    assert bad.status_code == 422
    assert tags(client, first["species_id"])[0]["observation_ids"] == [record["id"]]
    removed = client.delete(f"/api/observations/{record['id']}/species/{entries[1]['id']}")
    assert removed.status_code == 200, removed.text
    assert all(not v["linked"] for v in tags(client, first["species_id"]))
    assert tags(client, mixed["species_id"])[0]["observation_ids"] == [record["id"]]


def test_validation_rolls_back_new_species_and_behavior_tags(
    client, observation_payload, jpeg_bytes,
):
    payload = observation_payload()
    payload["behavior_labels"] = [" Flying ", "Ｆｌｙｉｎｇ"]
    response = client.post(
        "/api/observations", data={"payload": json.dumps(payload)},
        files={"photo": ("bird.jpg", jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 422
    assert client.get("/api/species").json() == []
    payload["behavior_labels"] = ["飞行"]
    first = create(client, payload, jpeg_bytes)
    tag = tags(client, first["species_id"])[0]
    # Reuse by normalized label on another observation, without duplicating the catalog.
    payload.update(species_id=first["species_id"], new_species=None, behavior_labels=[" 飞行 "])
    create(client, payload, jpeg_bytes)
    assert len(tags(client, first["species_id"])) == 1
    assert tags(client, first["species_id"])[0]["id"] == tag["id"]


def test_legacy_single_observation_links_migrate_without_losing_labels(
    tmp_path, observation_payload, jpeg_bytes,
):
    settings = Settings(_env_file=None, data_dir=tmp_path / "library")
    app = create_app(settings)
    with TestClient(app) as client:
        first = create(client, observation_payload(), jpeg_bytes)
        sid, oid = first["species_id"], first["observation_id"]
        assert client.put(f"/api/species/{sid}/profile", json={"behaviors": [
            {"label": "飞行", "observation_id": oid}, {"label": "捕食"},
        ]}).status_code == 200
    app.state.database.engine.dispose()
    with sqlite3.connect(settings.database_path) as db:
        db.execute("UPDATE species_behavior_tags SET observation_id=? WHERE label='飞行'", (oid,))
        db.execute("DROP TABLE observation_behaviors")
        db.execute("UPDATE alembic_version SET version_num='20260905_08'")
        original = db.execute("SELECT id,label FROM species_behavior_tags ORDER BY id").fetchall()
    with TestClient(create_app(settings)) as client:
        migrated = tags(client, sid)
        assert [(t["id"], t["label"]) for t in migrated] == original
        assert migrated[0]["observation_ids"] == [oid]
        assert migrated[1]["observation_ids"] == []
        assert client.get("/api/observations").json()[0]["behavior_labels"] == ["飞行"]
    assert list(settings.backups_dir.glob("pre-migration-*.sqlite"))
