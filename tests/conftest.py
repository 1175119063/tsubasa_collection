"""Shared browser fixtures and test data factories."""

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

EDGE_PATH = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def pytest_collection_modifyitems(items):
    """Mark direct and indirect browser fixture users before -m deselection."""
    for item in items:
        if "browser_app" in item.fixturenames:
            item.add_marker(pytest.mark.browser)


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


def post_observation(
    base_url: str,
    payload: dict | None = None,
    color=(73, 105, 82),
) -> dict:
    response = httpx.post(
        f"{base_url}/api/observations",
        data={"payload": json.dumps(payload or observation_payload(), ensure_ascii=False)},
        files={"photo": ("bird.jpg", jpeg_bytes(color), "image/jpeg")},
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


@pytest.fixture(name="jpeg_bytes")
def jpeg_bytes_factory():
    return jpeg_bytes


@pytest.fixture(name="observation_payload")
def observation_payload_factory():
    return observation_payload


@pytest.fixture(name="post_observation")
def post_observation_factory():
    return post_observation


@pytest.fixture(name="post_location")
def post_location_factory():
    return post_location


@pytest.fixture
def browser_app(tmp_path):
    from playwright.sync_api import sync_playwright

    if not EDGE_PATH.is_file():
        pytest.skip("浏览器流程测试需要 Microsoft Edge")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    data_dir = tmp_path / "library"
    app = create_app(Settings(_env_file=None, data_dir=data_dir))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
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
    finally:
        server.should_exit = True
        thread.join(timeout=10)
