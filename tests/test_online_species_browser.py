import json
from pathlib import Path

import httpx
from app.inat_mcp import inat_api
from app.online_species_service import OnlineSpeciesService
from playwright.sync_api import expect


def online_result():
    source = Path(__file__).resolve().parents[1] / "mcp-lab/fixtures/taxon_62148_zh.json"
    raw = json.loads(source.read_text("utf-8"))["results"][0]
    taxon = inat_api.normalize_taxon(raw, fetched_at="2026-10-23T08:00:00+08:00", cached=True)
    taxon = OnlineSpeciesService._enrich(taxon)
    return {
        "query": "须浮鸥",
        "resolved": True,
        "via": "query",
        "wikidata": None,
        "taxon": taxon,
        "candidates": [],
        "warnings": [],
    }


def rich_result():
    result = online_result()
    taxon = result["taxon"]
    taxon["children"] = [
        {
            "id": 204640,
            "name": "Chlidonias hybrida hybrida",
            "common_name": "须浮鸥（指名亚种）",
            "english_common_name": "Whiskered Tern",
            "rank": "subspecies",
            "is_active": True,
            "observations_count": 3500,
            "url": "https://www.inaturalist.org/taxa/204640",
            "photo": None,
        },
        {
            "id": 516848,
            "name": "Chlidonias hybrida delalandii",
            "common_name": "须浮鸥（非洲亚种）",
            "rank": "subspecies",
            "is_active": True,
            "observations_count": 3694,
            "url": "https://www.inaturalist.org/taxa/516848",
            "photo": None,
        },
    ]
    taxon["children_count"] = 2
    first = taxon["children"][0]
    result["ai"] = {
        "available": True,
        "message": "AI 仅按给定资料排序候选，不会自动选中或写入数据库。",
        "subspecies": [
            {
                **first,
                "confidence": "high",
                "reason": "上海附近 16 条亚种级记录全部为指名亚种。",
            }
        ],
        "warnings": [],
        "sources": ["iNaturalist", "Wikipedia"],
    }
    result["nearby"] = {
        "radius_km": 50,
        "total_results": 16,
        "returned": 16,
        "truncated": False,
        "counts": [
            {
                "taxon_id": 204640,
                "name": "Chlidonias hybrida hybrida",
                "common_name": "须浮鸥（指名亚种）",
                "rank": "subspecies",
                "count": 16,
            }
        ],
    }
    result["wikipedia"] = {
        "available": True,
        "title": "须浮鸥",
        "url": "https://zh.wikipedia.org/wiki/%E9%A1%BB%E6%B5%AE%E9%B8%A5",
        "lang": "zh",
        "excerpt": "须浮鸥繁殖于欧洲至中亚，冬季迁往非洲和南亚。",
        "fetched_at": "2026-11-03T08:00:00+08:00",
        "cached": False,
    }
    return result


def mock_model_offline(page):
    page.route(
        "**/api/assistant/status",
        lambda route: route.fulfill(
            json={"available": False, "message": "本地模型未启动"},
        ),
    )


def test_online_entry_preview_preserves_existing_fields(browser_app, tmp_path, jpeg_bytes):
    page, base_url, _ = browser_app
    mock_model_offline(page)
    result = online_result()
    page.route("**/api/assistant/online-species/search", lambda route: route.fulfill(json=result))
    page.goto(f"{base_url}/observations?new=1")
    dialog = page.locator("dialog.batch-dialog[open]")
    photo = tmp_path / "online.jpg"
    photo.write_bytes(jpeg_bytes())
    dialog.get_by_label("批量选择照片", exact=True).set_input_files(str(photo))
    dialog.locator("[data-new-species]").click()
    dialog.get_by_role("button", name="联网查物种", exact=True).click()
    dialog.get_by_label("该物种存在亚种", exact=True).check()
    dialog.get_by_label("完整亚种名单", exact=True).fill("Chlidonias hybrida hybrida | 指名亚种")
    dialog.get_by_label("IUCN 等级").select_option("LC")
    dialog.locator("[data-online-query]").fill("须浮鸥")
    dialog.locator("[data-online-search]").click()
    expect(dialog.locator("[data-online-detail]")).to_be_visible()
    expect(dialog.get_by_label("种拉丁学名", exact=True)).to_have_value("")
    dialog.locator("[data-online-apply]").click()
    expect(dialog.get_by_label("种拉丁学名", exact=True)).to_have_value("Chlidonias hybrida")
    expect(dialog.get_by_label("科拉丁学名", exact=True)).to_have_value("Laridae")
    expect(dialog.get_by_label("完整亚种名单", exact=True)).to_have_value(
        "Chlidonias hybrida hybrida | 指名亚种"
    )
    expect(dialog.get_by_label("IUCN 等级")).to_have_value("LC")
    # A conflicting existing path must not be combined with a new candidate.
    dialog.get_by_label("科拉丁学名", exact=True).fill("Corvidae")
    dialog.get_by_label("种拉丁学名", exact=True).fill("")
    dialog.locator("[data-online-search]").click()
    expect(dialog.locator("[data-online-apply]")).to_be_enabled()
    dialog.locator("[data-online-apply]").click()
    expect(dialog.get_by_text("已有分类与在线资料不一致", exact=False)).to_be_visible()
    expect(dialog.get_by_label("种拉丁学名", exact=True)).to_have_value("")
    expect(dialog.get_by_label("科拉丁学名", exact=True)).to_have_value("Corvidae")
    dialog.locator("[data-online-detail]").scroll_into_view_if_needed()
    page.screenshot(path=str(tmp_path / "online-entry.png"))


def test_online_species_shows_subspecies_ai_and_prefills_only_after_apply(
    browser_app, tmp_path, jpeg_bytes
):
    page, base_url, _ = browser_app
    mock_model_offline(page)
    page.route(
        "**/api/assistant/online-species/search",
        lambda route: route.fulfill(json=rich_result()),
    )
    page.goto(f"{base_url}/observations?new=1")
    dialog = page.locator("dialog.batch-dialog[open]")
    photo = tmp_path / "online-rich.jpg"
    photo.write_bytes(jpeg_bytes())
    dialog.get_by_label("批量选择照片", exact=True).set_input_files(str(photo))
    dialog.locator("[data-new-species]").click()
    dialog.get_by_role("button", name="联网查物种", exact=True).click()
    subspecies = dialog.get_by_label("该物种存在亚种", exact=True)
    expect(subspecies).not_to_be_checked()
    dialog.locator("[data-online-query]").fill("须浮鸥")
    dialog.locator("[data-online-search]").click()
    expect(dialog.locator("[data-online-subspecies]")).to_be_visible()
    expect(dialog.get_by_text("AI 建议 · 高置信", exact=False)).to_be_visible()
    expect(
        dialog.get_by_text("上海附近 16 条亚种级记录全部为指名亚种。", exact=False)
    ).to_be_visible()
    expect(
        dialog.locator(".online-nearby").get_by_text("16 条亚种级记录", exact=False)
    ).to_be_visible()
    expect(dialog.locator(".online-nearby").get_by_text("16 条", exact=True)).to_be_visible()
    expect(subspecies).not_to_be_checked()
    dialog.locator("[data-online-apply]").click()
    expect(subspecies).to_be_checked()
    expect(dialog.get_by_label("完整亚种名单", exact=True)).to_have_value(
        "Chlidonias hybrida hybrida | 须浮鸥（指名亚种）\n"
        "Chlidonias hybrida delalandii | 须浮鸥（非洲亚种）"
    )
    # Applying only fills the form; it must not save or close the observation dialog.
    expect(dialog).to_be_visible()
    page.screenshot(path=str(tmp_path / "online-subspecies-ai.png"))


def test_online_prefill_creates_new_species_with_subspecies(browser_app, tmp_path, jpeg_bytes):
    page, base_url, _ = browser_app
    mock_model_offline(page)
    page.route(
        "**/api/assistant/online-species/search",
        lambda route: route.fulfill(json=rich_result()),
    )
    page.goto(f"{base_url}/observations?new=1")
    dialog = page.locator("dialog.batch-dialog[open]")
    photo = tmp_path / "online-save.jpg"
    photo.write_bytes(jpeg_bytes())
    dialog.get_by_label("批量选择照片", exact=True).set_input_files(str(photo))
    dialog.locator("[data-new-species]").click()
    dialog.get_by_role("button", name="联网查物种", exact=True).click()
    dialog.locator("[data-online-query]").fill("须浮鸥")
    dialog.locator("[data-online-search]").click()
    expect(dialog.locator("[data-online-subspecies]")).to_be_visible()
    dialog.locator("[data-online-apply]").click()
    expect(dialog.get_by_label("该物种存在亚种", exact=True)).to_be_checked()

    form = dialog.locator("form")
    location = form.locator("fieldset").nth(1)
    location.get_by_label("拍摄时间", exact=True).fill("2026-08-26T07:15")
    location.get_by_label("纬度", exact=True).fill("31.230")
    location.get_by_label("经度", exact=True).fill("121.470")
    location.get_by_label("一级行政区代码", exact=True).fill("CN-SH")
    location.get_by_label("一级行政区名称", exact=True).fill("Shanghai")
    location.get_by_label("具体地点", exact=True).fill("Century Park")
    location.get_by_label("季节", exact=True).select_option("summer")

    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/observations") and response.request.method == "POST"
        )
    ) as saved:
        dialog.get_by_role("button", name="保存就绪照片（1）", exact=True).click()

    assert saved.value.status == 201
    created = saved.value.json()
    assert created["species_id"] > 0
    species = httpx.get(f"{base_url}/api/species/{created['species_id']}").json()
    assert species["scientific_name"] == "Chlidonias hybrida"
    assert species["has_subspecies"] is True
    assert {item["scientific_name"] for item in species["subspecies"]} == {
        "Chlidonias hybrida hybrida",
        "Chlidonias hybrida delalandii",
    }


def test_online_sidebar_candidates_retry_and_mobile(browser_app, tmp_path):
    page, base_url, _ = browser_app
    mock_model_offline(page)
    result = online_result()
    result.update(resolved=False, candidates=[result["taxon"]], taxon=None)
    attempts = []

    def search(route):
        attempts.append(route.request.post_data_json)
        if len(attempts) == 1:
            route.fulfill(status=504, json={"detail": "在线查询超时，请重试"})
        else:
            route.fulfill(json=result)

    page.route("**/api/assistant/online-species/search", search)
    page.route(
        "**/api/assistant/online-species/62148",
        lambda route: route.fulfill(json=online_result()["taxon"]),
    )
    page.goto(base_url)
    page.get_by_role("button", name="飞羽精灵", exact=True).click()
    panel = page.locator("#feather-panel")
    panel.get_by_role("button", name="联网查物种", exact=True).click()
    panel.locator("[data-online-query]").fill("须浮鸥")
    panel.locator("[data-online-search]").click()
    expect(panel.get_by_text("在线查询超时，请重试", exact=True)).to_be_visible()
    panel.locator("[data-online-search]").click()
    candidate = panel.get_by_role("button", name="查看资料", exact=False)
    expect(candidate).to_be_visible()
    expect(panel.locator("[data-online-detail]")).to_have_count(0)
    candidate.click()
    expect(panel.locator("[data-online-detail]")).to_be_visible()
    expect(
        panel.get_by_role("link", name="查看 iNaturalist 原始条目", exact=False)
    ).to_have_attribute("href", "https://www.inaturalist.org/taxa/62148")
    assert attempts == [{"query": "须浮鸥"}, {"query": "须浮鸥"}]
    page.screenshot(path=str(tmp_path / "online-sidebar-desktop.png"))
    page.set_viewport_size({"width": 390, "height": 844})
    assert panel.evaluate("el => el.scrollWidth <= el.clientWidth")
    page.screenshot(path=str(tmp_path / "online-sidebar-mobile.png"))
