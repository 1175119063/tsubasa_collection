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
