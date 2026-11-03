import json
from pathlib import Path

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
    dialog.locator("fieldset").first.locator("select").first.select_option("new")
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
