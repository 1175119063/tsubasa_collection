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




def test_assistant_previews_then_fills_new_species_taxonomy(browser_app):
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

    page.goto(f"{base_url}/observations?new=1")
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


def test_browser_can_create_observation_with_existing_species(browser_app, tmp_path):
    page, base_url, _data_dir = browser_app
    post_observation(base_url)
    photo_path = tmp_path / "vue-observation.jpg"
    photo_path.write_bytes(jpeg_bytes((92, 114, 78)))

    page.goto(f"{base_url}/observations?new=1")
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


def test_browser_can_edit_species_profile_and_open_audio_form(browser_app, tmp_path):
    page, base_url, _data_dir = browser_app
    created = post_observation(base_url)
    species_id = created["species_id"]
    page.goto(f"{base_url}/dex?species={species_id}")
    dossier = page.locator("dialog.v2-dossier[open]")
    dossier.wait_for(state="visible")
    dossier.get_by_role("button", name="修改图鉴").click()

    profile = page.locator("dialog.profile-dialog[open]")
    profile.wait_for(state="visible")
    profile.get_by_label("物种简介").fill("Vue 图鉴编辑流程测试。")
    with page.expect_response(
        lambda response: response.url.endswith(f"/api/species/{species_id}/profile")
        and response.request.method == "PUT"
    ) as profile_response:
        profile.get_by_role("button", name="保存图鉴资料").click()
    assert profile_response.value.status == 200
    profile.wait_for(state="hidden")
    dossier.get_by_text("Vue 图鉴编辑流程测试。", exact=True).wait_for()

    page.route(
        f"**/api/species/{species_id}/audio",
        lambda route: route.fulfill(status=201, json={"id": 1, "asset_id": 1}),
    )
    audio_path = tmp_path / "field-recording.mp3"
    audio_path.write_bytes(b"ID3")
    dossier.get_by_role("button", name="添加录音").click()
    audio_form = page.locator("dialog.record-dialog[open]")
    audio_form.wait_for(state="visible")
    audio_form.get_by_label("MP3 录音").set_input_files(str(audio_path))
    with page.expect_response(
        lambda response: response.url.endswith(f"/api/species/{species_id}/audio")
        and response.request.method == "POST"
    ) as audio_response:
        audio_form.get_by_role("button", name="保存录音").click()
    assert audio_response.value.status == 201
    audio_form.wait_for(state="hidden")


def test_browser_can_create_location_and_open_saved_detail(browser_app):
    page, base_url, _data_dir = browser_app
    page.goto(f"{base_url}/locations?new=1")
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
    page.wait_for_url("**/locations?location=*")
    assert "new=1" not in page.url
    assert len(httpx.get(f"{base_url}/api/locations").json()) == 1


def test_browser_can_create_trip_and_open_saved_detail(browser_app):
    page, base_url, _data_dir = browser_app
    post_location(base_url)
    page.goto(f"{base_url}/trips?new=1")
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
    page.wait_for_url("**/trips?trip=*")
    assert "new=1" not in page.url
    assert len(httpx.get(f"{base_url}/api/trips").json()) == 1


def test_browser_can_permanently_delete_observation(browser_app):
    page, base_url, _data_dir = browser_app
    post_observation(base_url)
    page.goto(f"{base_url}/observations")
    page.locator(".v2-field-card", has_text="白腰文鸟").click()
    detail = page.locator("dialog.v2-archive-dialog[open]")
    detail.wait_for(state="visible")
    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_response(
        lambda response: "/api/observations/" in response.url
        and response.request.method == "DELETE"
    ) as response_info:
        detail.get_by_role("button", name="永久删除").click()
    assert response_info.value.status == 200
    page.wait_for_url(f"{base_url}/observations")
    page.get_by_text("没有符合条件的记录", exact=True).wait_for(state="visible")
    assert httpx.get(f"{base_url}/api/observations").json() == []


def test_browser_can_restore_complete_backup(browser_app):
    page, base_url, data_dir = browser_app
    created = post_observation(base_url)
    page.goto(base_url)
    page.get_by_role("button", name="完整备份资料库").click()
    backup_dialog = page.get_by_role("dialog")
    backup_dialog.wait_for(state="visible")
    with page.expect_response(
        lambda response: response.url.endswith("/api/backups")
        and response.request.method == "POST"
    ) as backup_response:
        backup_dialog.get_by_role("button", name="立即创建完整备份").click()
    backup = backup_response.value.json()
    backup_path = data_dir.parent / "backups" / backup["filename"]
    assert backup_path.is_file()

    deleted = httpx.delete(f"{base_url}/api/observations/{created['observation_id']}")
    deleted.raise_for_status()
    backup_dialog.get_by_label("选择 ZIP 备份").set_input_files(str(backup_path))
    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_response(
        lambda response: response.url.endswith("/api/backups/restore")
    ) as restore_response:
        backup_dialog.get_by_role("button", name="校验并恢复备份").click()
    assert restore_response.value.status == 200
    backup_dialog.get_by_text("资料库已恢复", exact=False).wait_for()
    restored = httpx.get(f"{base_url}/api/observations").json()
    assert len(restored) == 1
    assert restored[0]["species_name"] == "白腰文鸟"


def test_browser_collection_plan_selects_crops_and_previews_evidence(browser_app):
    page, base_url, _data_dir = browser_app
    post_observation(base_url)
    page.goto(f"{base_url}/collections?new=1")
    plan_form = page.locator("dialog.collection-form-dialog[open]")
    plan_form.wait_for(state="visible")
    plan_form.get_by_label("计划名称").fill("文鸟观察集")
    plan_form.get_by_label("观察记录简介").fill("比较不同个体形态。")
    plan_form.get_by_text("性别与年龄", exact=True).click()
    with page.expect_response(
        lambda response: response.url.endswith("/api/collections")
        and response.request.method == "POST"
    ) as create_info:
        plan_form.get_by_role("button", name="保存计划").click()
    assert create_info.value.status == 201
    detail = page.locator("dialog.collection-detail-dialog[open]")
    detail.wait_for(state="visible")
    assert detail.get_by_text("计划中还没有鸟种", exact=True).is_visible()
    detail.get_by_role("button", name="添加鸟种", exact=False).click()
    member_dialog = page.locator("dialog.collection-member-dialog[open]")
    member_dialog.wait_for(state="visible")
    member_dialog.get_by_role("checkbox").check()
    with page.expect_response(
        lambda response: response.url.endswith("/species")
        and "/api/collections/" in response.url
        and response.request.method == "PUT"
    ) as members_info:
        member_dialog.get_by_role("button", name="保存鸟种").click()
    assert members_info.value.status == 200
    detail.get_by_role("button", name="为 白腰文鸟 ♂ 选择照片凭证").click()
    evidence = page.locator("dialog.collection-evidence-modal[open]")
    evidence.wait_for(state="visible")
    evidence.locator(".collection-evidence-list button").first.click()
    evidence.locator('input[type="range"]').fill("2")
    with page.expect_response(
        lambda response: "/api/collections/" in response.url
        and "/slots/" in response.url
        and response.request.method == "PUT"
    ) as response_info:
        evidence.get_by_role("button", name="保存头像").click()
    assert response_info.value.status == 200

    detail.get_by_role("button", name="设置计划 Logo", exact=False).click()
    logo_dialog = page.locator("dialog.collection-logo-modal[open]")
    logo_dialog.wait_for(state="visible")
    logo_dialog.locator(".collection-logo-candidates button").first.click()
    with page.expect_response(
        lambda response: response.url.endswith("/logo")
        and "/api/collections/" in response.url
        and response.request.method == "PUT"
    ) as logo_info:
        logo_dialog.get_by_role("button", name="保存 Logo").click()
    assert logo_info.value.status == 200
    assert detail.locator(".collection-logo-panel > img").is_visible()

    detail.get_by_role("button", name="查看 白腰文鸟 ♂ 的计划档案").click()
    preview = detail.locator(".collection-preview-panel")
    preview.get_by_role("heading", name="白腰文鸟", exact=True).wait_for(
        state="visible"
    )
    assert preview.get_by_text("梅花雀科", exact=True).is_visible()
    assert preview.get_by_text("IUCN LC · 无危", exact=True).is_visible()
    assert preview.get_by_role("link", name="查看这笔照片凭证").is_visible()
    preview.get_by_role("textbox").fill("记录它在文鸟专题中的辨识要点。")
    with page.expect_response(
        lambda response: response.url.endswith("/introduction")
        and "/api/collections/" in response.url
        and response.request.method == "PUT"
    ) as introduction_info:
        preview.get_by_role("button", name="保存简介").click()
    assert introduction_info.value.status == 200
    preview.get_by_text("专题简介已保存", exact=True).wait_for(state="visible")


def test_browser_collection_plan_without_subitems_uses_portrait_index(browser_app):
    page, base_url, _data_dir = browser_app
    response = httpx.post(
        f"{base_url}/api/collections",
        json={
            "name": "单幅鸟种陈列",
            "introduction": "每个物种只保留一张代表照片。",
            "template_kind": "none",
            "subitems": [],
        },
    )
    response.raise_for_status()
    plan = response.json()

    page.goto(f"{base_url}/collections?collection={plan['id']}")
    detail = page.locator("dialog.collection-detail-dialog[open]")
    detail.wait_for(state="visible")
    simple_index = detail.locator(".collection-simple-index")
    assert simple_index.is_visible()
    assert simple_index.get_by_text("收录物种", exact=True).is_visible()
    assert simple_index.get_by_text("已设照片", exact=True).is_visible()
    assert detail.get_by_text("装订进度", exact=True).count() == 0
    assert detail.get_by_text("统一模板", exact=True).count() == 0
