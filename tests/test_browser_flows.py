import io
import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from app.config import Settings
from app.main import create_app
from PIL import Image
from playwright.sync_api import sync_playwright

EDGE_PATH = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def jpeg_bytes(color=(73, 105, 82)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def observation_payload() -> dict:
    return {
        "species_id": None,
        "new_species": {
            "order": {"chinese_name": "雀形目", "scientific_name": "Passeriformes"},
            "family": {"chinese_name": "梅花雀科", "scientific_name": "Estrildidae"},
            "genus": {"chinese_name": "文鸟属", "scientific_name": "Lonchura"},
            "chinese_name": "白腰文鸟",
            "scientific_name": "Lonchura striata",
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
        "notes": "浏览器流程测试",
    }


def post_observation(base_url: str) -> dict:
    response = httpx.post(
        f"{base_url}/api/observations",
        data={"payload": json.dumps(observation_payload(), ensure_ascii=False)},
        files={"photo": ("bird.jpg", jpeg_bytes(), "image/jpeg")},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def post_location(base_url: str, name: str = "Test Wetland") -> dict:
    response = httpx.post(
        f"{base_url}/api/locations",
        json={
            "name": name,
            "location_type": "wetland_park",
            "country_code": "CN",
            "country_name": "China",
            "admin1_code": "CN-ZJ",
            "admin1_name": "Zhejiang",
            "city": "Hangzhou",
            "district": None,
            "center_latitude": 30.2741,
            "center_longitude": 120.1551,
            "coordinate_system": "wgs84",
            "radius_meters": 3000,
            "notes": None,
            "link_matching_records": False,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


@pytest.fixture
def browser_app(tmp_path):
    if not EDGE_PATH.is_file():
        pytest.skip("浏览器流程测试需要 Microsoft Edge")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    data_dir = tmp_path / "library"
    app = create_app(Settings(_env_file=None, data_dir=data_dir))
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("测试服务器未能启动")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(EDGE_PATH),
            headless=True,
        )
        page = browser.new_page()
        yield page, f"http://127.0.0.1:{port}", data_dir
        browser.close()
    server.should_exit = True
    thread.join(timeout=10)


def test_browser_can_create_observation(browser_app, tmp_path):
    page, base_url, _data_dir = browser_app
    photo_path = tmp_path / "browser-bird.jpg"
    photo_path.write_bytes(jpeg_bytes())

    page.goto(f"{base_url}/observations?new=1")
    page.locator("#record-dialog").wait_for(state="visible")
    page.locator("#species-select").select_option("new")
    for level in ("order", "family", "genus"):
        page.locator(f"#{level}-node-select").select_option("new")
    page.locator('input[name="order_chinese"]').fill("雀形目")
    page.locator('input[name="order_scientific"]').fill("Passeriformes")
    page.locator('input[name="family_chinese"]').fill("梅花雀科")
    page.locator('input[name="family_scientific"]').fill("Estrildidae")
    page.locator('input[name="genus_chinese"]').fill("文鸟属")
    page.locator('input[name="genus_scientific"]').fill("Lonchura")
    page.locator('input[name="species_chinese"]').fill("白腰文鸟")
    page.locator('input[name="species_scientific"]').fill("Lonchura striata")
    page.locator('select[name="china_status"]').select_option("three_protected")
    page.locator("#photo-input").set_input_files(str(photo_path))
    page.locator("#observed-at").fill("2026-08-15T08:30")
    page.locator('#record-form input[name="latitude"]').fill("30.2741")
    page.locator('#record-form input[name="longitude"]').fill("120.1551")
    page.locator('#record-form input[name="admin1_code"]').fill("CN-ZJ")
    page.locator('#record-form input[name="admin1_name"]').fill("浙江省")
    page.locator('#record-form input[name="locality"]').fill("杭州西湖")

    with page.expect_response(
        lambda response: response.url.endswith("/api/observations")
        and response.request.method == "POST"
    ) as response_info:
        page.locator('#record-form button[type="submit"]').click()
    assert response_info.value.status == 201
    page.locator(".v2-field-card", has_text="白腰文鸟").wait_for()


def test_browser_can_research_local_knowledge_and_fill_taxonomy(browser_app):
    page, base_url, _data_dir = browser_app
    page.route(
        "**/api/assistant/status",
        lambda route: route.fulfill(
            json={"enabled": True, "available": True, "message": "飞羽精灵已经醒来。"}
        ),
    )
    page.route(
        "**/api/assistant/taxonomy-research",
        lambda route: route.fulfill(
            json={
                "query": "蓝歌鸲",
                "extraction": {
                    "order": {"chinese_name": "雀形目", "scientific_name": "Passeriformes"},
                    "family": {"chinese_name": "鹟科", "scientific_name": "Muscicapidae"},
                    "genus": {"chinese_name": None, "scientific_name": "Larvivora"},
                    "species": {"chinese_name": "蓝歌鸲", "scientific_name": "Larvivora cyane"},
                    "subspecies": [],
                    "missing_fields": ["subspecies"],
                    "warnings": ["资料没有提供可确认的亚种"],
                },
                "citations": [
                    {
                        "source_id": "paper.pdf",
                        "title": "Local paper",
                        "locator": "片段 1",
                        "excerpt": "Larvivora cyane (Passeriformes: Muscicapidae)",
                    }
                ],
            }
        ),
    )

    page.goto(f"{base_url}/observations?new=1")
    page.locator("#record-dialog").wait_for(state="visible")
    page.locator("#species-select").select_option("new")
    research = page.locator("#feather-species-research")
    research.wait_for(state="visible")
    assert research.is_enabled()
    page.locator("#feather-species-query").fill("蓝歌鸲")
    research.click()
    page.locator("[data-feather-fill-species]").click()

    assert page.locator('input[name="species_chinese"]').input_value() == "蓝歌鸲"
    assert page.locator('input[name="species_scientific"]').input_value() == "Larvivora cyane"


def test_vue_assistant_previews_then_fills_new_species_taxonomy(browser_app):
    page, base_url, _data_dir = browser_app
    page.route(
        "**/api/assistant/status",
        lambda route: route.fulfill(
            json={"enabled": True, "available": True, "message": "ready"}
        ),
    )
    page.route(
        "**/api/assistant/taxonomy-research",
        lambda route: route.fulfill(
            json={
                "query": "Blue-and-white Flycatcher",
                "extraction": {
                    "order": {
                        "chinese_name": "雀形目",
                        "scientific_name": "Passeriformes",
                    },
                    "family": {
                        "chinese_name": "鹟科",
                        "scientific_name": "Muscicapidae",
                    },
                    "genus": {
                        "chinese_name": None,
                        "scientific_name": "Cyanoptila",
                    },
                    "species": {
                        "chinese_name": "白腹蓝鹟",
                        "scientific_name": "Cyanoptila cyanomelana",
                    },
                    "subspecies": [],
                    "missing_fields": ["subspecies"],
                    "warnings": ["No confirmed subspecies in the source."],
                },
                "citations": [
                    {
                        "source_id": "local-paper.pdf",
                        "title": "Local paper",
                        "locator": "fragment 1",
                        "excerpt": "Cyanoptila cyanomelana (Passeriformes: Muscicapidae)",
                    }
                ],
            }
        ),
    )

    page.goto(f"{base_url}/vue/observations?new=1")
    page.locator("dialog.record-dialog[open]").wait_for(state="visible")
    query = page.locator("[data-vue-feather-query]")
    query.wait_for(state="visible")
    query.fill("Blue-and-white Flycatcher")
    page.locator("[data-vue-feather-run]").click()

    output = page.locator("[data-vue-feather-output]")
    output.get_by_text("Cyanoptila cyanomelana", exact=False).first.wait_for()
    species_scientific = page.locator("fieldset").first.locator("input").nth(8)
    assert species_scientific.input_value() == ""

    page.locator("[data-vue-feather-apply]").click()
    assert species_scientific.input_value() == "Cyanoptila cyanomelana"


def test_vue_can_create_observation_with_existing_species(browser_app, tmp_path):
    page, base_url, _data_dir = browser_app
    post_observation(base_url)
    photo_path = tmp_path / "vue-observation.jpg"
    photo_path.write_bytes(jpeg_bytes((92, 114, 78)))

    page.goto(f"{base_url}/vue/observations?new=1")
    dialog = page.locator("dialog.record-dialog[open]")
    dialog.wait_for(state="visible")
    form = dialog.locator("form")
    form.locator('input[type="file"][accept*="image/jpeg"]').set_input_files(
        str(photo_path)
    )
    location_fields = form.locator("fieldset").nth(3).locator("input")
    location_fields.nth(0).fill("2026-08-26T07:15")
    location_fields.nth(1).fill("30.275")
    location_fields.nth(2).fill("120.156")
    location_fields.nth(5).fill("CN-ZJ")
    location_fields.nth(6).fill("Zhejiang")
    location_fields.nth(7).fill("West Lake")

    with page.expect_response(
        lambda response: response.url.endswith("/api/observations")
        and response.request.method == "POST"
    ) as response_info:
        form.locator('button[type="submit"]').click()
    assert response_info.value.status == 201
    page.locator("dialog.v2-archive-dialog[open]").wait_for(state="visible")
    assert len(httpx.get(f"{base_url}/api/observations").json()) == 2


def test_vue_can_create_location_and_open_saved_detail(browser_app):
    page, base_url, _data_dir = browser_app
    page.goto(f"{base_url}/vue/locations?new=1")
    dialog = page.locator("dialog.location-form-dialog[open]")
    dialog.wait_for(state="visible")
    form = dialog.locator("form")
    basic_fields = form.locator("fieldset").first.locator("input")
    basic_fields.nth(0).fill("Riverside Wetland")
    basic_fields.nth(4).fill("CN-ZJ")
    basic_fields.nth(5).fill("Zhejiang")
    coordinates = form.locator('input[type="number"]')
    coordinates.nth(1).fill("30.281")
    coordinates.nth(2).fill("120.162")

    with page.expect_response(
        lambda response: response.url.endswith("/api/locations")
        and response.request.method == "POST"
    ) as response_info:
        form.locator('button[type="submit"]').click()
    assert response_info.value.status == 201
    page.locator("dialog.v2-archive-dialog[open]").wait_for(state="visible")
    page.wait_for_url("**/vue/locations?location=*")
    assert "new=1" not in page.url
    assert len(httpx.get(f"{base_url}/api/locations").json()) == 1


def test_vue_can_create_trip_and_open_saved_detail(browser_app):
    page, base_url, _data_dir = browser_app
    post_location(base_url)
    page.goto(f"{base_url}/vue/trips?new=1")
    dialog = page.locator("dialog.trip-form-dialog[open]")
    dialog.wait_for(state="visible")
    form = dialog.locator("form")
    form.locator('input[type="text"]').fill("Autumn birding walk")
    date_fields = form.locator('input[type="datetime-local"]')
    date_fields.nth(0).fill("2026-08-26T06:30")
    date_fields.nth(1).fill("2026-08-26T10:00")

    with page.expect_response(
        lambda response: response.url.endswith("/api/trips")
        and response.request.method == "POST"
    ) as response_info:
        form.locator('button[type="submit"]').click()
    assert response_info.value.status == 201
    page.locator("dialog.v2-archive-dialog[open]").wait_for(state="visible")
    page.wait_for_url("**/vue/trips?trip=*")
    assert "new=1" not in page.url
    assert len(httpx.get(f"{base_url}/api/trips").json()) == 1


def test_browser_can_permanently_delete_observation(browser_app):
    page, base_url, _data_dir = browser_app
    post_observation(base_url)
    page.goto(f"{base_url}/observations")
    page.locator(".v2-field-card", has_text="白腰文鸟").click()
    page.locator("#v2-observation-dialog").wait_for(state="visible")
    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_response(
        lambda response: "/api/observations/" in response.url
        and response.request.method == "DELETE"
    ) as response_info:
        page.locator("[data-v2-delete-observation]").click()
    assert response_info.value.status == 200
    page.wait_for_url(f"{base_url}/observations")
    page.locator("#v2-observation-empty").wait_for(state="visible")
    assert httpx.get(f"{base_url}/api/observations").json() == []


def test_browser_can_restore_complete_backup(browser_app):
    page, base_url, data_dir = browser_app
    created = post_observation(base_url)
    page.goto(base_url)
    page.locator("#create-backup").click()
    with page.expect_response(
        lambda response: response.url.endswith("/api/backups")
        and response.request.method == "POST"
    ) as backup_response:
        page.locator("#confirm-backup").click()
    backup = backup_response.value.json()
    backup_path = data_dir.parent / "backups" / backup["filename"]
    assert backup_path.is_file()

    deleted = httpx.delete(f"{base_url}/api/observations/{created['observation_id']}")
    deleted.raise_for_status()
    page.locator("#restore-backup-file").set_input_files(str(backup_path))
    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_response(
        lambda response: response.url.endswith("/api/backups/restore")
    ) as restore_response:
        page.locator("#confirm-restore").click()
    assert restore_response.value.status == 200
    page.locator("#restore-status", has_text="资料库已恢复").wait_for()
    restored = httpx.get(f"{base_url}/api/observations").json()
    assert len(restored) == 1
    assert restored[0]["species_name"] == "白腰文鸟"
