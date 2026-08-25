import io
import json
import sqlite3
import zipfile

from app.assistant_schemas import AssistantSqlQuery
from app.config import Settings
from app.enums import MediaKind
from app.main import create_app
from app.models import MediaAsset, SpeciesAudio
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


class QueryPlanningAssistant:
    def plan_observation_query(self, _query: str) -> AssistantSqlQuery:
        return AssistantSqlQuery(
            interpretation="查询2026年8月15日的全部记录",
            sql=(
                "SELECT observation_id FROM field_observations "
                "WHERE observed_date = :day"
            ),
            parameters={"day": "2026-08-15"},
            sort="asc",
        )


def test_observation_query_skill_returns_exact_record_ids(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        app.state.feather_assistant = QueryPlanningAssistant()
        matching = post_observation(client, observation_payload())
        other_payload = observation_payload()
        other_payload["species_id"] = matching.json()["species_id"]
        other_payload["new_species"] = None
        other_payload["observed_at"] = "2026-08-16T08:30"
        other = post_observation(client, other_payload)
        assert other.status_code == 201

        response = client.post(
            "/api/assistant/search-parse",
            json={"query": "请查询2026年8月15日的全部记录"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["observation_ids"] == [matching.json()["observation_id"]]
    assert response.json()["result_count"] == 1
    assert response.json()["sort"] == "asc"


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


def profile_payload(observation_id: int) -> dict:
    return {
        "introduction": "常见于林缘，鸣声清脆。\n这是个人观察简介。",
        "order": {"chinese_name": "雀形目", "scientific_name": "Passeriformes"},
        "family": {"chinese_name": "梅花雀科", "scientific_name": "Estrildidae"},
        "genus": {"chinese_name": "文鸟属", "scientific_name": "Lonchura"},
        "ecological_group": "songbird",
        "body_size": "small_medium",
        "preferred_habitats": ["city", "forest", "wetland"],
        "evidence_selections": [
            {
                "dimension": "sex",
                "value_key": "male",
                "observation_id": observation_id,
            },
            {
                "dimension": "life_stage",
                "value_key": "adult",
                "observation_id": observation_id,
            },
        ],
        "behaviors": [
            {"label": "飞行", "observation_id": observation_id},
            {"label": "捕食", "observation_id": None},
        ],
        "individuals": [
            {"label": "雄性 · 成鸟 · 繁殖羽", "observation_id": observation_id},
            {"label": "非繁殖羽", "observation_id": None},
        ],
    }


def test_complete_demo_flow_and_species_id_is_never_reused(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        home_page = client.get("/")
        assert home_page.status_code == 200
        observations_page = client.get("/observations")
        dex_page = client.get("/dex")
        locations_page = client.get("/locations")
        trips_page = client.get("/trips")
        preview_page = client.get("/preview")
        preview_dex_page = client.get("/preview/dex")
        preview_observations_page = client.get("/preview/observations")
        preview_locations_page = client.get("/preview/locations")
        preview_trips_page = client.get("/preview/trips")
        legacy_page = client.get("/legacy")
        legacy_observations_page = client.get("/legacy/observations")
        legacy_dex_page = client.get("/legacy/dex")
        legacy_locations_page = client.get("/legacy/locations")
        legacy_trips_page = client.get("/legacy/trips")
        assert observations_page.status_code == 200
        assert dex_page.status_code == 200
        assert locations_page.status_code == 200
        assert trips_page.status_code == 200
        assert preview_page.status_code == 200
        assert preview_dex_page.status_code == 200
        assert preview_observations_page.status_code == 200
        assert preview_locations_page.status_code == 200
        assert preview_trips_page.status_code == 200
        legacy_pages = [
            legacy_page,
            legacy_observations_page,
            legacy_dex_page,
            legacy_locations_page,
            legacy_trips_page,
        ]
        assert all(page.status_code == 200 for page in legacy_pages)
        assert 'data-page="home"' in home_page.text
        assert "no-store" in home_page.headers["cache-control"]
        assert 'data-page="dex"' in dex_page.text
        assert 'data-page="observations"' in observations_page.text
        assert 'data-page="locations"' in locations_page.text
        assert 'data-page="trips"' in trips_page.text
        assert 'data-page="home"' in preview_page.text
        assert 'data-page="dex"' in preview_dex_page.text
        assert 'data-page="observations"' in preview_observations_page.text
        assert 'data-page="locations"' in preview_locations_page.text
        assert 'data-page="trips"' in preview_trips_page.text
        assert "/static/v2.css?v=" in preview_page.text
        assert "/static/v2.js?v=" in preview_dex_page.text
        assert 'id="v2-observation-groups"' in preview_observations_page.text
        assert 'id="v2-location-grid"' in preview_locations_page.text
        assert 'id="v2-trip-groups"' in preview_trips_page.text
        preview_pages_script = client.get("/static/v2-pages.js")
        assert preview_pages_script.status_code == 200
        assert "openObservation" in preview_pages_script.text
        assert "openLocation" in preview_pages_script.text
        assert "openTrip" in preview_pages_script.text
        assert preview_pages_script.text.count('class="v2-archive-danger-zone"') == 2
        assert "删除区域只会解除其中观察记录的关联" in preview_pages_script.text
        assert 'href="/locations"' in home_page.text
        assert "远征日志" in home_page.text
        assert 'href="/trips"' in home_page.text
        assert 'href="/legacy"' in home_page.text
        assert 'id="change-home-cover"' in home_page.text
        assert 'id="home-cover-dialog"' in home_page.text
        assert "/static/assets/wing-chronicle-logo.png" in home_page.text
        assert "/static/assets/wing-chronicle-logo.png" in dex_page.text
        assert "/static/assets/wing-chronicle-logo.png" in observations_page.text
        assert "/static/assets/wing-chronicle-logo.png" in locations_page.text
        assert "/static/assets/wing-chronicle-logo.png" in trips_page.text
        home_script = client.get("/static/v2.js").text
        assert 'Yuhen.api("/api/home/cover")' in home_script
        assert "data-home-cover-observation" in home_script
        assert 'id="new-location-button"' in locations_page.text
        assert 'id="location-grid"' in locations_page.text
        assert 'id="trip-groups"' in trips_page.text
        assert 'id="trip-observation-edit-dialog"' in trips_page.text
        trips_script = client.get("/static/trips.js").text
        assert "data-edit-trip-observations" in trips_script
        assert "filter((item) => !item.trip)" in trips_script
        assert "state.linkedObservationIds" in trips_script
        assert "new Set([...state.linkedObservationIds, ...selectedIds])" in trips_script
        assert 'id="trip-location-filter"' in trips_page.text
        assert 'id="observation-groups"' in observations_page.text
        assert 'id="observation-detail-dialog"' in observations_page.text
        assert 'id="observation-year-filter"' in observations_page.text
        assert 'id="species-search"' in observations_page.text
        assert 'id="species-search-status"' in observations_page.text
        assert 'id="species-search-results"' in observations_page.text
        assert 'id="species-selection-summary"' in observations_page.text
        assert 'id="order-node-search"' in observations_page.text
        assert 'id="family-node-search"' in observations_page.text
        assert 'id="genus-node-search"' in observations_page.text
        assert 'id="location-search"' in observations_page.text
        assert "/static/styles.css?v=" in observations_page.text
        assert "/static/observations.js?v=" in observations_page.text
        assert 'id="species-grid"' in dex_page.text
        assert 'id="family-filter"' in dex_page.text
        assert 'id="genus-filter"' in dex_page.text
        assert 'id="species-filter"' in dex_page.text
        assert 'id="profile-dialog"' in dex_page.text
        assert 'id="profile-behavior-list"' in dex_page.text
        assert 'id="profile-individual-list"' in dex_page.text
        assert 'id="add-individual-button"' in dex_page.text
        assert 'id="profile-ecology-options"' in dex_page.text
        assert 'id="profile-body-size-options"' in dex_page.text
        assert 'id="profile-habitat-options"' in dex_page.text
        assert 'id="species-audio-dialog"' in dex_page.text
        assert "/static/dex.js?v=" in dex_page.text
        assert "/observations?observation=" in client.get("/static/dex.js").text
        dex_script = client.get("/static/dex.js").text
        assert "data-edit-profile" in dex_script
        assert "species-observation-total" in dex_script
        assert "iucn-badge" in dex_script
        assert "data-individual-row" in dex_script
        assert "individuals" in dex_script
        assert "function ecologyPanel" in dex_script
        assert "preferred_habitats" in dex_script
        observations_script = client.get("/static/observations.js").text
        assert 'data-edit-observation="${item.id}"' in observations_script
        assert 'class="observation-preview-scroll"' in observations_script
        assert "data-species-result" in observations_script
        assert "function chooseSpecies" in observations_script
        assert "function chooseTaxonomy" in observations_script
        assert "function chooseLocation" in observations_script
        assert 'method: "PATCH"' in observations_script
        static_response = client.get("/static/observations.js")
        assert "no-store" in static_response.headers["cache-control"]
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
        assert detail["ecology"] == {
            "group": "unknown",
            "body_size": "unknown",
            "habitats": [],
        }
        assert "?thumbnail=true&v=" in detail["cover_url"]
        assert "?v=" in detail["cover"]["photo_url"]
        assert "?thumbnail=true&v=" in detail["observations"][0]["thumbnail_url"]

        media_response = client.get(detail["cover_url"])
        assert media_response.status_code == 200
        assert media_response.headers["content-type"].startswith("image/jpeg")
        assert "no-store" in media_response.headers["cache-control"]

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


def test_photo_larger_than_10_mb_is_rejected_and_temp_file_is_removed(tmp_path):
    data_dir = tmp_path / "library"
    app = create_app(Settings(data_dir=data_dir))
    oversized_photo = b"\xff\xd8" + b"0" * (10 * 1024 * 1024)

    with TestClient(app) as client:
        response = client.post(
            "/api/observations",
            data={"payload": json.dumps(observation_payload(), ensure_ascii=False)},
            files={"photo": ("bird.jpg", oversized_photo, "image/jpeg")},
        )
        assert response.status_code == 422
        assert "照片大小不能超过 10 MB" in response.text
        assert client.get("/api/species").json() == []

    assert list((data_dir / ".tmp").iterdir()) == []


def test_complete_backup_contains_consistent_database_and_media(tmp_path):
    data_dir = tmp_path / "library"
    app = create_app(Settings(data_dir=data_dir))
    with TestClient(app) as client:
        created = post_observation(client, observation_payload())
        assert created.status_code == 201
        response = client.post("/api/backups")
        assert response.status_code == 201, response.text
        backup = response.json()
        downloaded = client.get(backup["download_url"])
        assert downloaded.status_code == 200
        assert downloaded.headers["content-type"] == "application/zip"

    backup_path = tmp_path / "backups" / backup["filename"]
    assert backup_path.is_file()
    with zipfile.ZipFile(backup_path) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "data/database.sqlite" in names
        assert any(name.startswith("data/photos/") for name in names)
        assert any(name.startswith("data/thumbnails/") for name in names)
        archive.extract("data/database.sqlite", tmp_path / "restored")

    connection = sqlite3.connect(tmp_path / "restored" / "data" / "database.sqlite")
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT count(*) FROM observations").fetchone()[0] == 1
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        connection.close()


def test_complete_backup_restore_replaces_database_and_validates_media(tmp_path):
    data_dir = tmp_path / "library"
    app = create_app(Settings(data_dir=data_dir))
    with TestClient(app) as client:
        original = post_observation(client, observation_payload())
        backup = client.post("/api/backups").json()
        backup_path = tmp_path / "backups" / backup["filename"]

        assert client.delete(
            f"/api/observations/{original.json()['observation_id']}"
        ).status_code == 200
        replacement_payload = observation_payload("Passer montanus")
        replacement_payload["new_species"]["chinese_name"] = "树麻雀"
        replacement = post_observation(client, replacement_payload, color=(120, 80, 60))
        assert replacement.status_code == 201

        with backup_path.open("rb") as source:
            restored = client.post(
                "/api/backups/restore",
                files={"backup": (backup_path.name, source, "application/zip")},
            )

        assert restored.status_code == 200, restored.text
        assert restored.json()["restored"] is True
        assert restored.json()["safety_backup"]["filename"] != backup["filename"]
        observations = client.get("/api/observations").json()
        assert len(observations) == 1
        assert observations[0]["species_name"] == "白腰文鸟"
        assert client.get(observations[0]["photo_url"]).status_code == 200
        assert client.get(observations[0]["thumbnail_url"]).status_code == 200


def test_csv_export_contains_one_utf8_row_per_observed_species(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        created = post_observation(client, observation_payload())
        response = client.get("/api/exports/observations.csv")

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    text = response.content.decode("utf-8-sig")
    assert "observation_id,observed_at" in text
    assert "白腰文鸟" in text
    assert f"AV-{created.json()['species_id']:06d}" in text


def test_species_audio_can_be_deleted_and_unreferenced_file_is_removed(tmp_path):
    data_dir = tmp_path / "library"
    app = create_app(Settings(data_dir=data_dir))
    with TestClient(app) as client:
        created = post_observation(client, observation_payload())
        audio_path = data_dir / "audio" / "test-audio.mp3"
        audio_path.write_bytes(b"test-audio")
        with app.state.database.session_factory() as session:
            asset = MediaAsset(
                kind=MediaKind.AUDIO,
                sha256="0" * 64,
                relative_path="audio/test-audio.mp3",
                thumbnail_relative_path=None,
                original_filename="test-audio.mp3",
                mime_type="audio/mpeg",
                byte_size=10,
                width=None,
                height=None,
                duration_seconds=1.0,
            )
            session.add(asset)
            session.flush()
            link = SpeciesAudio(species_id=created.json()["species_id"], asset=asset)
            session.add(link)
            session.commit()
            audio_id = link.id

        response = client.delete(
            f"/api/species/{created.json()['species_id']}/audio/{audio_id}"
        )

        assert response.status_code == 200
        assert client.get(f"/api/species/{created.json()['species_id']}").json()[
            "species_audio"
        ] == []
        assert not audio_path.exists()


def test_map_overview_page_is_available(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        response = client.get("/map")

    assert response.status_code == 200
    assert 'id="region-overview-map"' in response.text
    assert "leaflet.markercluster" in response.text


def test_restore_rejects_tampered_media_without_changing_library(tmp_path):
    data_dir = tmp_path / "library"
    app = create_app(Settings(data_dir=data_dir))
    with TestClient(app) as client:
        created = post_observation(client, observation_payload())
        backup = client.post("/api/backups").json()
        source_path = tmp_path / "backups" / backup["filename"]
        tampered_path = tmp_path / "tampered.zip"
        with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(
            tampered_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for member in source.infolist():
                content = source.read(member.filename)
                if member.filename.startswith("data/photos/"):
                    content = b"tampered-photo"
                target.writestr(member, content)

        with tampered_path.open("rb") as source:
            response = client.post(
                "/api/backups/restore",
                files={"backup": ("tampered.zip", source, "application/zip")},
            )

        assert response.status_code == 422
        assert "校验失败" in response.text
        observations = client.get("/api/observations").json()
        assert [item["id"] for item in observations] == [created.json()["observation_id"]]
        assert client.get(observations[0]["photo_url"]).status_code == 200


def test_existing_database_is_registered_at_migration_baseline(tmp_path):
    data_dir = tmp_path / "library"
    data_dir.mkdir()
    connection = sqlite3.connect(data_dir / "database.sqlite")
    connection.execute(
        "CREATE TABLE birding_trips ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, location_id INTEGER NOT NULL, "
        "started_at DATETIME NOT NULL, ended_at DATETIME NOT NULL, notes TEXT)"
    )
    connection.commit()
    connection.close()

    app = create_app(Settings(data_dir=data_dir))
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    connection = sqlite3.connect(data_dir / "database.sqlite")
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(birding_trips)")}
        assert "name" in columns
        location_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(birding_locations)")
        }
        assert "coordinate_system" in location_columns
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
            "20260822_04"
        )
    finally:
        connection.close()
    migration_snapshots = list((tmp_path / "backups").glob("pre-migration-*.sqlite"))
    assert len(migration_snapshots) == 1
    snapshot = sqlite3.connect(migration_snapshots[0])
    try:
        assert snapshot.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert "alembic_version" not in {
            row[0]
            for row in snapshot.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        snapshot.close()


def test_one_observation_can_record_multiple_species(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        first = post_observation(client, observation_payload())
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
        second = post_observation(client, second_payload, color=(120, 100, 80))
        assert first.status_code == 201 and second.status_code == 201

        multi_payload = observation_payload()
        multi_payload["species_id"] = first.json()["species_id"]
        multi_payload["new_species"] = None
        multi_payload["observed_at"] = "2026-08-16T08:30"
        multi_payload["additional_species"] = [{
            "species_id": second.json()["species_id"],
            "photo_type": "group",
            "sex": None,
            "life_stage": None,
            "subspecies_id": None,
            "notes": "画面左侧约三只",
        }]
        created = post_observation(client, multi_payload, color=(80, 110, 95))
        assert created.status_code == 201, created.text
        assert len(created.json()["species_entries"]) == 2

        observation = next(
            item for item in client.get("/api/observations").json()
            if item["id"] == created.json()["observation_id"]
        )
        assert observation["species_count"] == 2
        assert {entry["species_name"] for entry in observation["species_entries"]} == {
            "白腰文鸟", "树麻雀"
        }
        secondary = next(
            entry for entry in observation["species_entries"] if not entry["is_primary"]
        )
        assert secondary["photo_type"] == "group"
        assert secondary["notes"] == "画面左侧约三只"
        first_detail = client.get(f"/api/species/{first.json()['species_id']}").json()
        second_detail = client.get(f"/api/species/{second.json()['species_id']}").json()
        assert first_detail["observation_count"] == 2
        assert second_detail["observation_count"] == 2

        removed = client.delete(
            f"/api/observations/{observation['id']}/species/{secondary['id']}"
        )
        assert removed.status_code == 200
        assert removed.json()["removed_species"] is False
        updated = next(
            item for item in client.get("/api/observations").json()
            if item["id"] == observation["id"]
        )
        assert updated["species_count"] == 1

        cannot_remove_last = client.delete(
            f"/api/observations/{updated['id']}/species/"
            f"{updated['species_entries'][0]['id']}"
        )
        assert cannot_remove_last.status_code == 422

        added = client.post(
            f"/api/observations/{updated['id']}/species",
            json={
                "species_id": second.json()["species_id"],
                "photo_type": "individual",
                "sex": "unknown",
                "life_stage": "unknown",
                "subspecies_id": None,
                "notes": "编辑器后加物种",
            },
        )
        assert added.status_code == 201, added.text
        assert added.json()["species_count"] == 2
        primary = next(
            entry for entry in added.json()["species_entries"] if entry["is_primary"]
        )
        removed_primary = client.delete(
            f"/api/observations/{updated['id']}/species/{primary['id']}"
        )
        assert removed_primary.status_code == 200, removed_primary.text
        promoted = next(
            item for item in client.get("/api/observations").json()
            if item["id"] == observation["id"]
        )
        assert promoted["species_count"] == 1
        assert promoted["species_entries"][0]["is_primary"] is True
        assert promoted["species_name"] == "树麻雀"


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


def test_homepage_cover_can_be_pinned_and_return_to_latest(tmp_path):
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

        automatic = client.get("/api/home/cover")
        assert automatic.status_code == 200
        assert automatic.json()["selection_mode"] == "latest"
        assert automatic.json()["observation"]["id"] == second.json()["observation_id"]

        pinned = client.put(
            "/api/home/cover",
            json={"observation_id": first.json()["observation_id"]},
        )
        assert pinned.status_code == 200
        assert pinned.json()["selection_mode"] == "manual"
        assert pinned.json()["observation"]["id"] == first.json()["observation_id"]
        assert client.get("/api/home/cover").json()["observation"]["id"] == first.json()[
            "observation_id"
        ]

        deleted = client.delete(
            f"/api/observations/{first.json()['observation_id']}"
        )
        assert deleted.status_code == 200
        fallback = client.get("/api/home/cover").json()
        assert fallback["selection_mode"] == "latest"
        assert fallback["observation"]["id"] == second.json()["observation_id"]

        reset = client.put("/api/home/cover", json={"observation_id": None})
        assert reset.status_code == 200
        assert reset.json()["selection_mode"] == "latest"
        assert reset.json()["observation"]["id"] == second.json()["observation_id"]


def test_species_profile_archives_keep_links_and_fall_back_after_deletion(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        first = post_observation(client, observation_payload())
        second_payload = observation_payload()
        second_payload["species_id"] = first.json()["species_id"]
        second_payload["new_species"] = None
        second_payload["observed_at"] = "2026-08-16T09:10"
        second = post_observation(client, second_payload, color=(120, 90, 65))
        species_id = first.json()["species_id"]
        second_id = second.json()["observation_id"]

        payload = profile_payload(second_id)
        payload["family"]["chinese_name"] = "梅花雀科（更正）"
        response = client.put(f"/api/species/{species_id}/profile", json=payload)
        assert response.status_code == 200, response.text
        detail = response.json()
        assert detail["introduction"].startswith("常见于林缘")
        assert detail["classification"]["family"]["chinese_name"] == "梅花雀科（更正）"
        assert detail["collected"]["sexes"][0]["observation_id"] == second_id
        assert detail["collected"]["life_stages"][0]["observation_id"] == second_id
        assert detail["behaviors"][0]["label"] == "飞行"
        assert detail["behaviors"][0]["observation_id"] == second_id
        assert detail["behaviors"][1]["linked"] is False
        assert detail["ecology"] == {
            "group": "songbird",
            "body_size": "small_medium",
            "habitats": ["city", "forest", "wetland"],
        }
        custom_individual = next(
            item for item in detail["individuals"] if item["label"] == "雄性 · 成鸟 · 繁殖羽"
        )
        assert custom_individual["observation_id"] == second_id

        payload["ecological_group"] = "waterfowl"
        payload["body_size"] = "medium"
        payload["preferred_habitats"] = ["river", "lake"]
        updated_again = client.put(f"/api/species/{species_id}/profile", json=payload)
        assert updated_again.status_code == 200, updated_again.text
        assert updated_again.json()["ecology"] == {
            "group": "waterfowl",
            "body_size": "medium",
            "habitats": ["lake", "river"],
        }

        deleted = client.delete(f"/api/observations/{second_id}")
        assert deleted.status_code == 200
        detail = client.get(f"/api/species/{species_id}").json()
        assert detail["collected"]["sexes"][0]["observation_id"] == first.json()[
            "observation_id"
        ]
        assert detail["behaviors"][0]["label"] == "飞行"
        assert detail["behaviors"][0]["linked"] is False
        custom_individual = next(
            item for item in detail["individuals"] if item["label"] == "雄性 · 成鸟 · 繁殖羽"
        )
        assert custom_individual["linked"] is False


def test_species_profile_rejects_mismatched_archive_evidence(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        created = post_observation(client, observation_payload())
        payload = profile_payload(created.json()["observation_id"])
        payload["evidence_selections"][0]["value_key"] = "female"
        response = client.put(
            f"/api/species/{created.json()['species_id']}/profile", json=payload
        )
        assert response.status_code == 422
        assert "观察与对应档案项不一致" in response.text


def test_species_profile_rejects_more_than_three_habitats(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "library"))
    with TestClient(app) as client:
        created = post_observation(client, observation_payload())
        payload = profile_payload(created.json()["observation_id"])
        payload["preferred_habitats"] = ["city", "farmland", "forest", "wetland"]
        response = client.put(
            f"/api/species/{created.json()['species_id']}/profile", json=payload
        )
        assert response.status_code == 422


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
        assert location["coordinate_system"] == "wgs84"
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
                "name": "西湖清晨寻鸟",
                "location_id": location["id"],
                "started_at": "2026-08-15T08:00",
                "ended_at": "2026-08-15T11:00",
                "notes": "清晨观鸟",
            },
        )
        assert trip.status_code == 201, trip.text
        trip_data = trip.json()
        trip_id = trip_data["id"]
        assert trip_data["name"] == "西湖清晨寻鸟"
        assert trip_data["custom_name"] == "西湖清晨寻鸟"
        assert client.get("/api/trips").json()[0]["name"] == "西湖清晨寻鸟"

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
        assert first_observation["trip"]["name"] == "西湖清晨寻鸟"

        cover = client.put(
            f"/api/trips/{trip_id}/cover",
            json={"observation_id": second.json()["observation_id"]},
        )
        assert cover.status_code == 200
        assert cover.json()["cover_observation_id"] == second.json()["observation_id"]

        unlinked = client.put(
            f"/api/trips/{trip_id}/observations",
            json={"observation_ids": [first.json()["observation_id"]]},
        )
        assert unlinked.status_code == 200
        assert unlinked.json()["observation_count"] == 1
        assert unlinked.json()["cover_observation_id"] == first.json()["observation_id"]

        renamed = client.put(
            f"/api/trips/{trip_id}",
            json={
                "name": "西湖夏末远征",
                "location_id": location["id"],
                "started_at": "2026-08-15T08:00",
                "ended_at": "2026-08-15T11:00",
                "notes": "更名后的远征",
            },
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "西湖夏末远征"

        second_location_payload = location_payload()
        second_location_payload["name"] = "杭州植物园"
        second_location_payload["center_latitude"] = 30.252
        second_location = client.post(
            "/api/locations", json=second_location_payload
        ).json()
        multi_location = client.put(
            f"/api/trips/{trip_id}",
            json={
                "name": "西湖夏末远征",
                "location_ids": [second_location["id"], location["id"]],
                "primary_location_id": second_location["id"],
                "started_at": "2026-08-15T08:00",
                "ended_at": "2026-08-15T11:00",
                "notes": "两处地点",
            },
        )
        assert multi_location.status_code == 200, multi_location.text
        assert multi_location.json()["location_count"] == 2
        assert [item["id"] for item in multi_location.json()["locations"]] == [
            second_location["id"], location["id"]
        ]
        assert multi_location.json()["location"]["id"] == second_location["id"]
        related_location = client.get(
            f"/api/locations/{location['id']}"
        ).json()
        assert related_location["trip_count"] == 1
        assert related_location["trips"][0]["id"] == trip_id
        assert related_location["trips"][0]["is_primary_location"] is False
        assert renamed.json()["custom_name"] == "西湖夏末远征"

        invalid_update = client.put(
            f"/api/trips/{trip_id}",
            json={
                "location_id": location["id"],
                "started_at": "2026-08-15T08:00",
                "ended_at": "2026-08-15T08:15",
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
        assert other_trip["name"] == location["name"]
        assert other_trip["custom_name"] is None
        conflict = client.put(
            f"/api/trips/{other_trip['id']}/observations",
            json={"observation_ids": [first.json()["observation_id"]]},
        )
        assert conflict.status_code == 409

        deleted = client.delete(f"/api/trips/{trip_id}")
        assert deleted.status_code == 200
        assert deleted.json()["unlinked_observation_count"] == 1
        assert all(item["trip"] is None for item in client.get("/api/observations").json())
