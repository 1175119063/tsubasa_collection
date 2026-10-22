import httpx
import pytest
from playwright.sync_api import expect


@pytest.mark.parametrize("missing_step", ["preview", "save"])
def test_old_backend_reports_restart_and_keeps_taxonomy_draft(
    browser_app, missing_step, post_observation
):
    page, base_url, _ = browser_app
    post_observation(base_url)
    genus_id = httpx.get(f"{base_url}/api/species").json()[0]["genus_id"]
    page.goto(f"{base_url}/dex?view=taxonomy&rank=genus&node={genus_id}")
    page.get_by_role("button", name="修改分类", exact=True).click()
    editor = page.locator("dialog.taxonomy-edit-dialog[open]")
    editor.get_by_label("中文名", exact=True).fill("文鸟属更正")
    preview = editor.get_by_role("button", name="预览修改影响", exact=True)
    save = editor.get_by_role("button", name="确认保存分类", exact=True)
    endpoint = f"**/api/taxonomy/genus/{genus_id}"
    blocked = endpoint + "/preview" if missing_step == "preview" else endpoint
    page.route(blocked, lambda route: route.fulfill(status=404, json={"detail": "Not Found"}))
    preview.click()
    if missing_step == "save":
        save.click()
    expect(editor.get_by_role("alert")).to_contain_text("请重启本地服务")
    expect(editor.get_by_label("中文名", exact=True)).to_have_value("文鸟属更正")
    expect(save).to_be_disabled()
    page.unroute(blocked)
    preview.click()
    expect(save).to_be_enabled()
    save.click()
    expect(editor).to_have_count(0)
    expect(page.locator("[data-taxonomy-current]")).to_contain_text("文鸟属更正")


def test_tree_rename_and_move_branch_with_impact_preview(
    browser_app, tmp_path, observation_payload, post_observation
):
    page, base_url, _ = browser_app
    first = post_observation(base_url)
    second = observation_payload()
    second["new_species"]["scientific_name"] = "Lonchura punctulata"
    post_observation(base_url, second)
    target = observation_payload()
    target["new_species"].update(
        {
            "chinese_name": "喜鹊",
            "scientific_name": "Pica serica",
            "family": {"chinese_name": "鸦科", "scientific_name": "Corvidae"},
            "genus": {"chinese_name": "鹊属", "scientific_name": "Pica"},
        }
    )
    post_observation(base_url, target)
    species = httpx.get(f"{base_url}/api/species").json()
    genus_id = next(item["genus_id"] for item in species if item["id"] == first["species_id"])
    page.goto(f"{base_url}/dex?view=taxonomy&rank=genus&node={genus_id}")
    page.get_by_role("button", name="修改分类", exact=True).click()
    editor = page.locator("dialog.taxonomy-edit-dialog[open]")
    save = editor.get_by_role("button", name="确认保存分类", exact=True)
    expect(save).to_be_disabled()
    editor.get_by_label("中文名", exact=True).fill("文鸟属更正")
    editor.get_by_role("button", name="预览修改影响", exact=True).click()
    expect(editor.get_by_label("修改影响预览")).to_contain_text("涉及 2 个物种、2 笔观察")
    save.click()
    expect(editor).to_have_count(0)
    expect(page.locator("[data-taxonomy-current]")).to_contain_text("文鸟属更正")
    assert f"node={genus_id}" in page.url
    page.get_by_role("button", name="修改分类", exact=True).click()
    editor.get_by_role("combobox", name="操作", exact=True).select_option("move")
    editor.get_by_role("searchbox").fill("corvidae")
    editor.locator(".taxonomy-parent-results button").click()
    editor.get_by_role("button", name="预览修改影响", exact=True).click()
    expect(editor.get_by_label("修改影响预览")).to_contain_text("鸦科")
    expect(editor.get_by_role("heading", name="修改影响预览")).to_be_in_viewport()
    page.screenshot(path=str(tmp_path / "taxonomy-move-preview.png"))
    save.click()
    expect(editor).to_have_count(0)
    expect(page.locator("[data-taxonomy-parent]")).to_contain_text("鸦科")
    assert len(httpx.get(f"{base_url}/api/observations").json()) == 3


def test_species_move_from_tree_and_profile_save(
    browser_app, tmp_path, observation_payload, post_observation
):
    page, base_url, _ = browser_app
    first = post_observation(base_url)
    second = observation_payload()
    second["new_species"]["scientific_name"] = "Lonchura punctulata"
    other = post_observation(base_url, second)
    page.goto(f"{base_url}/dex?view=taxonomy&rank=species&node={first['species_id']}")
    page.get_by_role("button", name="修改分类", exact=True).click()
    editor = page.locator("dialog.taxonomy-edit-dialog[open]")
    editor.get_by_role("combobox", name="操作", exact=True).select_option("move")
    editor.get_by_role("combobox", name="目标分类", exact=True).select_option(
        label="补建缺少的分类"
    )
    editor.get_by_role("searchbox").fill("梅花雀科")
    editor.locator(".taxonomy-parent-results button").click()
    editor.locator(".taxonomy-new-parent").get_by_label("中文名", exact=True).fill("新属")
    latin = editor.locator(".taxonomy-new-parent").get_by_label("拉丁学名", exact=True)
    latin.fill("NewGenus")
    editor.get_by_role("button", name="预览修改影响", exact=True).click()
    expect(editor.get_by_label("修改影响预览")).to_contain_text("涉及 1 个物种、1 笔观察")
    latin.fill("CorrectedGenus")
    expect(editor.get_by_role("button", name="确认保存分类")).to_be_disabled()
    editor.get_by_role("button", name="预览修改影响", exact=True).click()
    editor.get_by_role("button", name="确认保存分类", exact=True).click()
    expect(editor).to_have_count(0)
    expect(page.locator("[data-taxonomy-parent]")).to_contain_text("新属")
    page.goto(f"{base_url}/dex?species={first['species_id']}")
    page.get_by_role("button", name="修改图鉴", exact=True).click()
    profile = page.locator("dialog.profile-dialog[open]")
    expect(profile.get_by_role("group", name="02 分类信息")).to_have_count(0)
    expect(profile.get_by_role("button", name="修改当前物种分类", exact=True)).to_have_count(0)
    profile.get_by_label("物种简介", exact=True).fill("观察心得")
    page.screenshot(path=str(tmp_path / "profile-notes.png"))
    profile.get_by_role("button", name="保存图鉴资料", exact=True).click()
    expect(profile).to_have_count(0)
    changed = httpx.get(f"{base_url}/api/species/{first['species_id']}").json()
    unchanged = httpx.get(f"{base_url}/api/species/{other['species_id']}").json()
    assert changed["classification"]["genus"]["scientific_name"] == "CorrectedGenus"
    assert unchanged["classification"]["genus"]["scientific_name"] == "Lonchura"
    assert changed["introduction"] == "观察心得"
