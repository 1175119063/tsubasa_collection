import io

import httpx
import pytest
from PIL import Image
from playwright.sync_api import expect


def photo_file(tmp_path, name, captured_at, color=(65, 100, 80)):
    path = tmp_path / name
    exif = Image.Exif()
    exif[306] = captured_at
    buffer = io.BytesIO()
    Image.new("RGB", (900, 600), color).save(buffer, format="JPEG", exif=exif)
    path.write_bytes(buffer.getvalue())
    return path


def open_batch(page, base_url, paths):
    page.goto(f"{base_url}/observations")
    page.get_by_role("button", name="＋ 登记新发现", exact=True).click()
    dialog = page.locator("dialog.batch-dialog[open]")
    dialog.get_by_label("批量选择照片", exact=True).set_input_files([str(path) for path in paths])
    expect(dialog.locator(".batch-footer")).to_contain_text("照片已加入")
    return dialog


def fill_common(dialog, species_id, location_id):
    form = dialog.locator("form.batch-entry-form")
    form.locator("fieldset").nth(0).locator("select").first.select_option(str(species_id))
    location_fields = form.locator("fieldset").nth(3)
    location_fields.locator("select").first.select_option(str(location_id))
    form.get_by_label("季节", exact=True).select_option("summer")


def apply_common(dialog):
    dialog.locator(".batch-apply").get_by_label("地点与坐标", exact=True).check()
    dialog.locator(".batch-apply").get_by_label("季节", exact=True).check()
    dialog.locator(".batch-apply").get_by_role("button").click()


def assert_search_results_inline(page, field, search_label, select_label):
    picker = field.locator(".species-picker")
    picker.scroll_into_view_if_needed()
    search = picker.get_by_role("searchbox", name=search_label, exact=True).bounding_box()
    results = picker.get_by_role("list", name=f"{search_label}结果").bounding_box()
    select = picker.get_by_role("combobox", name=select_label, exact=True).bounding_box()
    assert results["y"] >= search["y"] + search["height"]
    assert results["y"] + results["height"] <= select["y"]
    assert results["x"] >= search["x"] - 1
    assert results["width"] <= search["width"] + 2
    first = picker.get_by_role("list").get_by_role("button").first
    expect(first).to_be_in_viewport()
    assert first.evaluate("""button => {
        const rect = button.getBoundingClientRect();
        return button.contains(document.elementFromPoint(
            rect.x + rect.width / 2, rect.y + rect.height / 2
        ));
    }""")
    return first


@pytest.mark.parametrize("multiple", [True, False], ids=["button-multiple", "direct-single"])
def test_species_search_selects_primary_and_other_species(
    browser_app, tmp_path, multiple, observation_payload, post_location, post_observation
):
    page, base_url, _ = browser_app
    munia = post_observation(base_url)
    payload = observation_payload()
    payload["new_species"].update(
        {
            "chinese_name": "喜鹊",
            "scientific_name": "Pica serica",
            "family": {"chinese_name": "鸦科", "scientific_name": "Corvidae"},
            "genus": {"chinese_name": "鹊属", "scientific_name": "Pica"},
        }
    )
    magpie = post_observation(base_url, payload)
    location = post_location(base_url)
    first = photo_file(tmp_path, "search-first.jpg", "2026:08:25 07:10:00")
    second = photo_file(tmp_path, "search-second.jpg", "2026:08:25 08:20:00")
    if multiple:
        dialog = open_batch(page, base_url, [first, second])
    else:
        page.goto(f"{base_url}/observations?new=1")
        dialog = page.locator("dialog.batch-dialog[open]")
        dialog.locator('input[type="file"][accept*="image/jpeg"]').set_input_files(str(first))
    form = dialog.locator("form")
    primary = form.locator("fieldset").nth(0)
    others = form.locator("fieldset").nth(2)
    query = primary.get_by_label("搜索已有图鉴物种", exact=True)
    choice = primary.get_by_role("combobox", name="选择图鉴物种", exact=True)
    for term in ["喜鹊", "  PICA   SERICA  ", "鸦科", "corvidae", "鹊属", magpie["catalog_number"]]:
        query.fill(term)
        expect(primary.get_by_role("list").get_by_role("button")).to_have_count(1)
        expect(primary.get_by_role("list")).to_contain_text("喜鹊")
    query.fill("a")
    expect(primary.get_by_role("list").get_by_role("button")).to_have_count(2)
    assert_search_results_inline(page, primary, "搜索已有图鉴物种", "选择图鉴物种")
    query.fill("喜鹊")
    result_button = assert_search_results_inline(page, primary, "搜索已有图鉴物种", "选择图鉴物种")
    page.screenshot(path=str(tmp_path / "species-search.png"))
    # Click where a person sees the result, without locator auto-scrolling it into view.
    box = result_button.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(choice).to_have_value(str(magpie["species_id"]))
    query.fill("喜鹊")
    # Keyboard users can also choose a search result without opening the native select.
    query.press("Tab")
    page.keyboard.press("Enter")
    expect(choice).to_have_value(str(magpie["species_id"]))
    expect(query).to_have_value("")
    query.fill("不存在的鸟")
    expect(primary.get_by_role("status")).to_contain_text("没有找到")
    expect(choice).to_have_value(str(magpie["species_id"]))
    query.fill("")
    expect(choice.locator("option")).to_have_count(4)

    other_query = others.get_by_label("搜索照片中的其他物种", exact=True)
    other_query.fill("喜鹊")
    expect(others.get_by_role("status")).to_contain_text("没有找到")
    other_query.fill("ＬＯＮＣＨＵＲＡ")
    assert_search_results_inline(page, others, "搜索照片中的其他物种", "选择已有图鉴物种")
    others.get_by_role("list").get_by_role("button").click()
    expect(others.get_by_role("combobox", name="选择已有图鉴物种", exact=True)).to_have_value(
        str(munia["species_id"])
    )
    others.get_by_role("button", name="＋ 添加到这笔观察", exact=True).click()
    expect(others.locator(".additional-species-entry")).to_contain_text("白腰文鸟")
    other_query.fill("文鸟")
    expect(others.get_by_role("status")).to_contain_text("没有找到")
    others.get_by_role("button", name="移除", exact=True).click()
    expect(others.get_by_role("list").get_by_role("button")).to_have_count(1)
    others.get_by_role("list").get_by_role("button").click()
    others.get_by_role("button", name="＋ 添加到这笔观察", exact=True).click()
    expect(others.locator(".additional-species-entry")).to_have_count(1)
    form.locator(".observation-photo-species").get_by_label("白腰文鸟", exact=True).check()
    form.locator("fieldset").nth(3).locator("select").first.select_option(str(location["id"]))
    form.get_by_label("季节", exact=True).select_option("summer")
    if multiple:
        dialog.locator(".batch-photo-button").nth(1).click()
        expect(choice).to_have_value("")
        expect(others.locator(".additional-species-entry")).to_have_count(0)
        dialog.locator(".batch-photo-button").nth(0).click()
        expect(choice).to_have_value(str(magpie["species_id"]))
        expect(others.locator(".additional-species-entry")).to_contain_text("白腰文鸟")
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/observations") and response.request.method == "POST"
        )
    ) as saved:
        dialog.get_by_role("button", name="保存就绪照片（1）", exact=True).click()
    assert saved.value.status == 201
    result = saved.value.json()
    assert result["species_id"] == magpie["species_id"]
    response = httpx.get(f"{base_url}/api/observations")
    response.raise_for_status()
    detail = next(item for item in response.json() if item["id"] == result["observation_id"])
    assert {entry["species_id"] for entry in detail["species_entries"]} == {
        munia["species_id"],
        magpie["species_id"],
    }


def test_new_discovery_entries_and_unsaved_close_guard(browser_app, tmp_path):
    page, base_url, _ = browser_app
    page.goto(f"{base_url}/")
    page.get_by_role("link", name="登记新发现", exact=True).click()
    dialog = page.locator("dialog.batch-dialog[open]")
    expect(dialog.get_by_role("heading", name="登记新发现", exact=True)).to_be_visible()
    dialog.get_by_role("button", name="关闭登记新发现", exact=True).click()
    expect(dialog).to_have_count(0)
    page.wait_for_url(f"{base_url}/observations")
    expect(page.get_by_role("button", name="批量导入照片", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="＋ 登记新发现", exact=True)).to_have_count(1)
    page.get_by_role("button", name="登记第一笔观察", exact=True).click()
    expect(dialog.get_by_role("heading", name="登记新发现", exact=True)).to_be_visible()
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    page.get_by_role("button", name="＋ 登记新发现", exact=True).click()
    photo = photo_file(tmp_path, "unsaved.jpg", "2026:08:25 07:10:00")
    dialog.get_by_label("批量选择照片", exact=True).set_input_files(str(photo))
    expect(dialog.locator(".batch-items li")).to_have_count(1)
    page.once("dialog", lambda prompt: prompt.dismiss())
    dialog.get_by_role("button", name="关闭登记新发现", exact=True).click()
    expect(dialog.locator(".batch-items li")).to_have_count(1)
    page.once("dialog", lambda prompt: prompt.accept())
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)


def test_batch_reuses_fields_preserves_exif_and_keeps_invalid_files_separate(
    browser_app, tmp_path, post_location, post_observation
):
    page, base_url, _ = browser_app
    original = post_observation(base_url)
    location = post_location(base_url)
    first = photo_file(tmp_path, "first.jpg", "2026:08:25 07:10:00")
    second = photo_file(tmp_path, "second.jpg", "2026:08:25 08:20:00", (90, 80, 65))
    broken = tmp_path / "broken.jpg"
    broken.write_text("not a jpeg", encoding="utf-8")
    dialog = open_batch(page, base_url, [first, second, broken])
    form = dialog.locator("form.batch-entry-form")
    assert form.locator("fieldset").first.locator("select").first.input_value() == ""
    assert form.get_by_label("季节", exact=True).input_value() == ""
    expect(dialog.get_by_role("button", name="保存就绪照片（0）")).to_be_disabled()
    fill_common(dialog, original["species_id"], location["id"])
    apply_common(dialog)
    dialog.locator(".batch-photo-button").nth(1).click()
    assert form.get_by_label("拍摄时间", exact=True).input_value() == "2026-08-25T08:20"
    form.locator("fieldset").nth(1).locator("select").nth(1).select_option("female")
    form.get_by_label("备注", exact=True).fill("second photo note")
    dialog.locator(".batch-photo-button").nth(0).click()
    assert form.get_by_label("拍摄时间", exact=True).input_value() == "2026-08-25T07:10"
    dialog.get_by_role("button", name="保存就绪照片（2）").click()
    expect(dialog.locator('.batch-item[data-state="saved"]')).to_have_count(2)
    expect(dialog.locator(".batch-footer")).to_contain_text("本批已保存 2 / 3 张")
    expect(dialog.get_by_role("button", name="保存就绪照片（0）")).to_be_disabled()
    records = httpx.get(f"{base_url}/api/observations").json()
    assert len(records) == 3
    imported = sorted(
        (item for item in records if item["id"] != original["observation_id"]),
        key=lambda item: item["observed_at"],
    )
    assert [item["observed_at"][:16] for item in imported] == [
        "2026-08-25T07:10",
        "2026-08-25T08:20",
    ]
    assert all(item["season"] == "summer" for item in imported)
    assert all(item["location"]["id"] == location["id"] for item in imported)
    assert imported[0]["sex"] == "unknown"
    assert imported[1]["sex"] == "female"
    assert imported[1]["notes"] == "second photo note"
    dialog.locator(".batch-photo-button").nth(2).click()
    expect(dialog.locator(".batch-issues")).to_contain_text("JPEG")
    page.screenshot(path=str(tmp_path / "batch-import.png"), full_page=True)


def test_batch_new_species_is_created_once_and_failed_photo_can_retry(
    browser_app, tmp_path, post_location, post_observation
):
    page, base_url, _ = browser_app
    post_observation(base_url)
    location = post_location(base_url)
    first = photo_file(tmp_path, "new-first.jpg", "2026:08:25 07:10:00")
    second = photo_file(tmp_path, "new-second.jpg", "2026:08:25 08:20:00")
    dialog = open_batch(page, base_url, [first, second])
    form = dialog.locator("form.batch-entry-form")
    fill_common(dialog, "new", location["id"])
    taxonomy = httpx.get(f"{base_url}/api/taxonomy/tree").json()
    species_fields = form.locator("fieldset").first
    species_fields.locator("select").nth(1).select_option(str(taxonomy[0]["id"]))
    species_fields.locator("select").nth(2).select_option(str(taxonomy[0]["families"][0]["id"]))
    species_fields.locator("select").nth(3).select_option(
        str(taxonomy[0]["families"][0]["genera"][0]["id"])
    )
    form.get_by_label("种中文名", exact=True).fill("批量测试文鸟")
    form.get_by_label("种拉丁学名", exact=True).fill("Lonchura batchtest")
    apply_common(dialog)
    requests = []

    def fail_first_request(route):
        if route.request.method != "POST":
            route.continue_()
            return
        requests.append(route.request.post_data_buffer)
        if len(requests) == 1:
            route.fulfill(status=422, json={"detail": "test rejection"})
        else:
            route.continue_()

    page.route("**/api/observations", fail_first_request)
    dialog.get_by_role("button", name="保存就绪照片（2）").click()
    expect(dialog.locator('.batch-item[data-state="saved"]')).to_have_count(1)
    expect(dialog.locator('.batch-item[data-state="error"]')).to_have_count(1)
    retry = dialog.get_by_role("button", name="保存就绪照片（1）")
    expect(retry).to_be_enabled()
    retry.click()
    expect(dialog.locator('.batch-item[data-state="saved"]')).to_have_count(2)
    expect(dialog.get_by_role("button", name="保存就绪照片（0）")).to_be_disabled()
    records = httpx.get(f"{base_url}/api/observations").json()
    assert len(records) == 3
    new_species = [
        item
        for item in httpx.get(f"{base_url}/api/species").json()
        if item["scientific_name"] == "Lonchura batchtest"
    ]
    assert len(new_species) == 1
    assert new_species[0]["observation_count"] == 2
    assert len(requests) == 3
    assert b'"new_species":null' in requests[-1]


def test_batch_unknown_save_result_stops_queue_and_cannot_resubmit(
    browser_app, tmp_path, post_location, post_observation
):
    page, base_url, _ = browser_app
    original = post_observation(base_url)
    location = post_location(base_url)
    first = photo_file(tmp_path, "uncertain.jpg", "2026:08:25 07:10:00")
    second = photo_file(tmp_path, "waiting.jpg", "2026:08:25 08:20:00")
    dialog = open_batch(page, base_url, [first, second])
    fill_common(dialog, original["species_id"], location["id"])
    apply_common(dialog)
    page.evaluate("""() => {
        const originalFetch = window.fetch.bind(window);
        window.testObservationSaves = 0;
        window.fetch = async (url, options) => {
            const response = await originalFetch(url, options);
            if (url === '/api/observations' && options?.method === 'POST') {
                window.testObservationSaves += 1;
                await response.text();
                throw new TypeError('Test: response lost after server commit');
            }
            return response;
        };
    }""")
    dialog.get_by_role("button", name="保存就绪照片（2）").click()
    expect(dialog.locator('.batch-item[data-state="uncertain"]')).to_have_count(1)
    expect(dialog.get_by_role("button", name="保存就绪照片（1）")).to_be_disabled()
    expect(dialog.locator(".batch-footer")).to_contain_text("待核实")
    assert page.evaluate("window.testObservationSaves") == 1
    assert len(httpx.get(f"{base_url}/api/observations").json()) == 2


def test_batch_trip_retry_preserves_existing_members_without_resaving_photos(
    browser_app, tmp_path, post_location, post_observation
):
    page, base_url, _ = browser_app
    original = post_observation(base_url)
    location = post_location(base_url)
    trip_payload = {
        "name": "Batch Trip",
        "location_id": location["id"],
        "location_ids": [location["id"]],
        "started_at": "2026-08-15T00:00",
        "ended_at": "2026-08-16T23:00",
        "notes": None,
    }
    response = httpx.post(f"{base_url}/api/trips", json=trip_payload)
    assert response.status_code == 201, response.text
    trip = response.json()
    response = httpx.put(
        f"{base_url}/api/trips/{trip['id']}/observations",
        json={"observation_ids": [original["observation_id"]]},
    )
    assert response.status_code == 200, response.text
    photo = photo_file(tmp_path, "trip-photo.jpg", "2026:08:25 07:10:00")
    dialog = open_batch(page, base_url, [photo])
    fill_common(dialog, original["species_id"], location["id"])
    dialog.get_by_role("button", name="保存就绪照片（1）").click()
    expect(dialog.locator('.batch-item[data-state="saved"]')).to_have_count(1)
    trip_box = dialog.locator(".batch-trip")
    trip_box.locator("select").select_option(str(trip["id"]))
    link = trip_box.get_by_role("button", name="关联本批已保存照片")
    expect(link).to_be_enabled()
    link.click()
    expect(trip_box).to_contain_text("时间不在行程范围内")
    assert len(httpx.get(f"{base_url}/api/observations").json()) == 2
    trip_payload["ended_at"] = "2026-08-26T23:00"
    response = httpx.put(f"{base_url}/api/trips/{trip['id']}", json=trip_payload)
    assert response.status_code == 200, response.text
    link.click()
    expect(trip_box).to_contain_text("原有观察已保留")
    detail = httpx.get(f"{base_url}/api/trips/{trip['id']}").json()
    assert len(detail["observations"]) == 2
    assert original["observation_id"] in {item["id"] for item in detail["observations"]}
    assert len(httpx.get(f"{base_url}/api/observations").json()) == 2
    page.set_viewport_size({"width": 390, "height": 844})
    expect(dialog.get_by_role("button", name="关闭登记新发现")).to_be_visible()
    assert dialog.evaluate("element => element.scrollWidth <= element.clientWidth + 1")
    page.screenshot(path=str(tmp_path / "batch-mobile.png"), full_page=True)


def test_batch_pause_finishes_current_photo_and_resumes_remaining_queue(
    browser_app, tmp_path, post_location, post_observation
):
    page, base_url, _ = browser_app
    original = post_observation(base_url)
    location = post_location(base_url)
    first = photo_file(tmp_path, "pause-first.jpg", "2026:08:25 07:10:00")
    second = photo_file(tmp_path, "pause-second.jpg", "2026:08:25 08:20:00")
    dialog = open_batch(page, base_url, [first, second])
    fill_common(dialog, original["species_id"], location["id"])
    apply_common(dialog)
    page.evaluate("""() => {
        const originalFetch = window.fetch.bind(window);
        let delayed = false;
        window.fetch = async (url, options) => {
            const response = await originalFetch(url, options);
            if (url === '/api/observations' && options?.method === 'POST' && !delayed) {
                delayed = true;
                await new Promise(resolve => { window.releaseBatchResponse = resolve; });
            }
            return response;
        };
    }""")
    dialog.get_by_role("button", name="保存就绪照片（2）").click()
    page.wait_for_function("typeof window.releaseBatchResponse === 'function'")
    dialog.get_by_role("button", name="暂停保存", exact=True).click()
    page.evaluate("window.releaseBatchResponse()")
    expect(dialog.locator(".batch-footer")).to_contain_text("已暂停")
    expect(dialog.locator('.batch-item[data-state="saved"]')).to_have_count(1)
    assert len(httpx.get(f"{base_url}/api/observations").json()) == 2
    dialog.get_by_role("button", name="保存就绪照片（1）").click()
    expect(dialog.locator('.batch-item[data-state="saved"]')).to_have_count(2)
    assert len(httpx.get(f"{base_url}/api/observations").json()) == 3
