import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from test_demo_flow import observation_payload, post_observation, profile_payload


@pytest.fixture
def taxonomy_client(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path / "library"))) as client:
        for name in ["Lonchura striata", "Lonchura punctulata", "Pica serica"]:
            payload = observation_payload(name)
            if name.startswith("Pica"):
                payload["new_species"].update({
                    "chinese_name": "喜鹊",
                    "family": {"chinese_name": "鸦科", "scientific_name": "Corvidae"},
                    "genus": {"chinese_name": "鹊属", "scientific_name": "Pica"},
                })
            result = post_observation(client, payload)
            assert result.status_code == 201, result.text
        yield client


def edit(client, rank, node_id, payload):
    endpoint = f"/api/taxonomy/{rank}/{node_id}"
    preview = client.post(endpoint + "/preview", json=payload)
    assert preview.status_code == 200, preview.text
    saved = client.put(endpoint, json={**payload, "preview_token": preview.json()["preview_token"]})
    assert saved.status_code == 200, saved.text
    return preview.json()


def test_rename_and_species_move_preserve_identity_and_observations(taxonomy_client):
    client = taxonomy_client
    species = client.get("/api/species").json()
    first, second, target = sorted(species, key=lambda item: item["id"])
    before = client.get("/api/observations").json()
    rename = {"action": "rename", "name": {
        "chinese_name": "文鸟属更正", "scientific_name": "LonchuraCorrected",
    }}
    preview = edit(client, "genus", first["genus_id"], rename)
    assert preview["species_count"] == preview["observation_count"] == 2
    assert client.get("/api/species").json()[0]["genus_id"] == first["genus_id"]
    preview = edit(client, "species", first["id"], {
        "action": "move", "parent_id": target["genus_id"],
    })
    assert preview["species_count"] == preview["observation_count"] == 1
    current = {item["id"]: item for item in client.get("/api/species").json()}
    assert current[first["id"]]["genus_id"] == target["genus_id"]
    assert current[second["id"]]["genus_id"] == first["genus_id"]
    for item in species:
        assert current[item["id"]]["catalog_number"] == item["catalog_number"]
        assert current[item["id"]]["scientific_name"] == item["scientific_name"]
    after = client.get("/api/observations").json()
    for old, new in zip(before, after, strict=True):
        for field in ["id", "photos", "audio", "notes", "observed_at", "species_entries"]:
            assert old[field] == new[field]


def test_move_branch_prunes_only_empty_ancestors(taxonomy_client):
    client = taxonomy_client
    species = sorted(client.get("/api/species").json(), key=lambda item: item["id"])
    preview = edit(client, "genus", species[0]["genus_id"], {
        "action": "move", "parent_id": species[2]["family_id"],
    })
    assert preview["species_count"] == 2
    tree = client.get("/api/taxonomy/tree").json()
    assert len(tree[0]["families"]) == 1
    assert len(tree[0]["families"][0]["genera"]) == 2
    assert len(client.get("/api/observations").json()) == 3


def test_new_ancestors_are_atomic_and_stale_preview_is_rejected(taxonomy_client):
    client = taxonomy_client
    item = client.get("/api/species").json()[0]
    endpoint = f"/api/taxonomy/species/{item['id']}"
    payload = {"action": "move", "new_parents": [
        {"chinese_name": "新目", "scientific_name": "NewOrder"},
        {"chinese_name": "新科", "scientific_name": "NewFamily"},
        {"chinese_name": "新属", "scientific_name": "NewGenus"},
    ]}
    original_tree = client.get("/api/taxonomy/tree").json()
    preview = client.post(endpoint + "/preview", json=payload).json()
    assert client.get("/api/taxonomy/tree").json() == original_tree
    observation = observation_payload()
    observation.update({"species_id": item["id"], "new_species": None})
    assert post_observation(client, observation).status_code == 201
    rejected = client.put(endpoint, json={**payload, "preview_token": preview["preview_token"]})
    assert rejected.status_code == 409
    assert client.get("/api/taxonomy/tree").json() == original_tree
    preview = edit(client, "species", item["id"], payload)
    assert preview["observation_count"] == 2
    assert len(client.get("/api/taxonomy/tree").json()) == 2


def test_duplicate_invalid_target_and_legacy_profile_cannot_modify_tree(taxonomy_client):
    client = taxonomy_client
    first, _, target = sorted(client.get("/api/species").json(), key=lambda item: item["id"])
    before = client.get("/api/taxonomy/tree").json()
    endpoint = f"/api/taxonomy/genus/{first['genus_id']}/preview"
    conflict = client.post(endpoint, json={"action": "rename", "name": {
        "chinese_name": "冲突", "scientific_name": "  PICA  ",
    }})
    assert conflict.status_code == 409
    assert client.post(endpoint, json={"action": "move", "parent_id": 99999}).status_code == 404
    root_edit = client.post("/api/taxonomy/class/aves/preview", json={"action": "move"})
    assert root_edit.status_code == 422
    assert client.post("/api/taxonomy/order/1/preview", json={
        "action": "move", "parent_id": target["family_id"],
    }).status_code == 422
    payload = profile_payload(1)
    payload["family"]["chinese_name"] = "意外更改"
    assert client.put(f"/api/species/{first['id']}/profile", json=payload).status_code == 409
    assert client.get("/api/taxonomy/tree").json() == before
