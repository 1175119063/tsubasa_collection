import httpx
from playwright.sync_api import expect


def test_create_edit_and_manage_behaviors_from_both_pages(
    browser_app, tmp_path, observation_payload, jpeg_bytes, post_observation, post_location,
):
    page, base, _ = browser_app
    payload = observation_payload()
    payload["behavior_labels"] = ["飞行"]
    first = post_observation(base, payload)
    sid = first["species_id"]
    location = post_location(base)
    photo = tmp_path / "new-behaviors.jpg"
    photo.write_bytes(jpeg_bytes((92, 114, 78)))
    page.goto(f"{base}/observations?new=1")
    dialog = page.locator("dialog.batch-dialog[open]")
    dialog.get_by_label("批量选择照片", exact=True).set_input_files(str(photo))
    form = dialog.locator("form")
    form.get_by_role("combobox", name="选择图鉴物种", exact=True).select_option(str(sid))
    fields = form.locator("fieldset").nth(3)
    fields.locator("select").first.select_option(str(location["id"]))
    fields.locator('input[type="datetime-local"]').fill("2026-10-22T08:30")
    form.get_by_label("季节", exact=True).select_option("autumn")
    picker = form.locator(".behavior-picker")
    picker.get_by_label("飞行", exact=True).check()
    picker.get_by_label("新行为标签", exact=True).fill("捕食")
    picker.get_by_role("button", name="添加并选中").click()
    expect(picker.get_by_label("捕食", exact=True)).to_be_checked()
    picker.scroll_into_view_if_needed()
    page.screenshot(path=str(tmp_path / "behavior-create.png"))
    dialog.get_by_role("button", name="保存就绪照片（1）", exact=True).click()
    expect(dialog.locator(".batch-item")).to_have_attribute("data-state", "saved")
    records = httpx.get(f"{base}/api/observations").json()
    second = next(item for item in records if item["id"] != first["observation_id"])
    assert second["behavior_labels"] == ["飞行", "捕食"]
    dialog.get_by_role("button", name="关闭登记新发现", exact=True).click()
    page.goto(f"{base}/observations?observation={second['id']}&species={sid}")
    detail = page.locator("dialog.observation-detail-dialog[open]")
    expect(detail).to_contain_text("飞行、捕食")
    detail.get_by_role("button", name="修改记录", exact=True).click()
    editor = page.locator("dialog.observation-editor-dialog[open]")
    editor.get_by_label("飞行", exact=True).uncheck()
    editor.get_by_label("新行为标签", exact=True).fill("理羽")
    editor.get_by_role("button", name="添加并选中").click()
    editor.get_by_role("button", name="保存修改", exact=True).click()
    expect(editor).not_to_be_visible()
    expect(detail).to_contain_text("捕食、理羽")
    page.goto(f"{base}/dex?species={sid}")
    dossier = page.locator("dialog.v2-dossier[open]")
    expect(dossier.locator(".dossier-behaviors")).to_contain_text("理羽")
    dossier.get_by_role("button", name="修改图鉴", exact=True).click()
    profile = page.locator("dialog.profile-dialog[open]")
    # Stable catalog order: existing flying, feeding, then preening.
    flying = profile.locator(".profile-behavior-entry").nth(0)
    flying.get_by_label("行为标签", exact=True).fill("盘旋")
    for checkbox in flying.get_by_role("checkbox").all():
        checkbox.check()
    flying.scroll_into_view_if_needed()
    page.screenshot(path=str(tmp_path / "behavior-profile.png"))
    profile.get_by_role("button", name="保存图鉴资料", exact=True).click()
    expect(profile).not_to_be_visible()
    tag = dossier.locator(".dossier-behavior").filter(has_text="盘旋")
    expect(tag).to_contain_text("2 笔观察")
    expect(tag.get_by_role("link")).to_have_count(2)
    records = httpx.get(f"{base}/api/observations").json()
    assert all("盘旋" in record["behavior_labels"] for record in records)
    dossier.get_by_role("button", name="修改图鉴", exact=True).click()
    profile.locator(".profile-behavior-entry").nth(0).get_by_role(
        "button", name="删除行为标签", exact=True,
    ).click()
    profile.get_by_role("button", name="保存图鉴资料", exact=True).click()
    expect(profile).not_to_be_visible()
    records = httpx.get(f"{base}/api/observations").json()
    assert len(records) == 2
    assert all("盘旋" not in record["behavior_labels"] for record in records)


def test_behavior_link_focuses_the_associated_species(
    browser_app, observation_payload, post_observation,
):
    page, base, _ = browser_app
    original = post_observation(base)
    sid = original["species_id"]
    payload = observation_payload()
    payload["new_species"].update(chinese_name="斑文鸟", scientific_name="Lonchura punctulata")
    payload["additional_species"] = [{
        "species_id": sid, "photo_type": "group", "behavior_labels": ["捕食"],
    }]
    mixed = post_observation(base, payload)
    page.goto(f"{base}/dex?species={sid}")
    behavior = page.locator(".dossier-behavior").filter(has_text="捕食")
    behavior.get_by_role("link").click()
    detail = page.locator("dialog.observation-detail-dialog[open]")
    expect(detail.get_by_role("heading", name="白腰文鸟", exact=True)).to_be_visible()
    expect(detail).to_contain_text("捕食")
    assert f"species={sid}" in page.url
    assert f"observation={mixed['observation_id']}" in page.url


def test_automatic_evidence_and_custom_label_do_not_override_each_other(
    browser_app, observation_payload, post_observation,
):
    page, base, _ = browser_app
    first = post_observation(base)
    sid, first_id = first["species_id"], first["observation_id"]
    payload = observation_payload()
    payload.update(species_id=sid, new_species=None, observed_at="2026-10-22T08:30")
    second = post_observation(base, payload)
    saved = httpx.put(f"{base}/api/species/{sid}/profile", json={
        "individuals": [{"label": "生命阶段 · 成鸟", "observation_id": first_id}],
    })
    saved.raise_for_status()
    page.goto(f"{base}/dex?species={sid}")
    dossier = page.locator("dialog.v2-dossier[open]")
    dossier.get_by_role("button", name="修改图鉴", exact=True).click()
    profile = page.locator("dialog.profile-dialog[open]")
    profile.locator(".profile-evidence-row").filter(has_text="生命阶段 · 成鸟").locator(
        "select"
    ).select_option(str(second["observation_id"]))
    profile.get_by_role("button", name="保存图鉴资料", exact=True).click()
    expect(profile).not_to_be_visible()
    auto = dossier.locator('[data-profile-evidence="automatic"]').get_by_role(
        "link", name="生命阶段 · 成鸟", exact=True,
    )
    custom = dossier.locator('[data-profile-evidence="custom"]').get_by_role(
        "link", name="生命阶段 · 成鸟", exact=True,
    )
    assert f"observation={second['observation_id']}" in auto.get_attribute("href")
    assert f"observation={first_id}" in custom.get_attribute("href")


def test_editing_behaviors_stays_with_species_when_switching_and_removing(
    browser_app, observation_payload, post_observation,
):
    page, base, _ = browser_app
    first = post_observation(base)
    payload = observation_payload()
    payload["new_species"].update(chinese_name="斑文鸟", scientific_name="Lonchura punctulata")
    payload["behavior_labels"] = ["飞行"]
    payload["additional_species"] = [{
        "species_id": first["species_id"], "photo_type": "group", "behavior_labels": ["捕食"],
    }]
    mixed = post_observation(base, payload)
    oid = mixed["observation_id"]
    page.goto(f"{base}/observations?observation={oid}")
    detail = page.locator("dialog.observation-detail-dialog[open]")
    detail.get_by_role("button", name="修改记录", exact=True).click()
    editor = page.locator("dialog.observation-editor-dialog[open]")
    picker = editor.locator(".behavior-picker")
    choice = editor.get_by_role("combobox", name="正在编辑的物种", exact=True)
    picker.get_by_label("新行为标签", exact=True).fill("理羽")
    picker.get_by_role("button", name="添加并选中").click()
    choice.select_option("1")
    expect(picker.get_by_label("捕食", exact=True)).to_be_checked()
    expect(picker.get_by_label("理羽", exact=True)).to_have_count(0)
    picker.get_by_label("新行为标签", exact=True).fill("休息")
    picker.get_by_role("button", name="添加并选中").click()
    choice.select_option("0")
    expect(picker.get_by_label("理羽", exact=True)).to_be_checked()
    expect(picker.get_by_label("休息", exact=True)).to_have_count(0)
    editor.get_by_role("button", name="保存修改", exact=True).click()
    expect(editor).not_to_be_visible()
    record = next(v for v in httpx.get(f"{base}/api/observations").json() if v["id"] == oid)
    assert record["species_entries"][0]["behavior_labels"] == ["飞行", "理羽"]
    assert record["species_entries"][1]["behavior_labels"] == ["捕食", "休息"]
    detail.get_by_role("button", name="修改记录", exact=True).click()
    choice.select_option("1")
    page.once("dialog", lambda dialog: dialog.accept())
    editor.get_by_role("button", name="删除当前物种信息", exact=True).click()
    expect(choice).to_have_value("0")
    expect(picker.get_by_label("理羽", exact=True)).to_be_checked()
    expect(picker.get_by_label("休息", exact=True)).to_have_count(0)
    editor.get_by_role("button", name="保存修改", exact=True).click()
    expect(editor).not_to_be_visible()
    record = next(v for v in httpx.get(f"{base}/api/observations").json() if v["id"] == oid)
    assert len(record["species_entries"]) == 1
    assert record["behavior_labels"] == ["飞行", "理羽"]
