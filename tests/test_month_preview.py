import httpx
from playwright.sync_api import expect
from test_browser_flows import browser_app as browser_app
from test_browser_flows import post_observation


def test_month_preview_expands_independently_and_respects_filters(browser_app, tmp_path):
    page, base_url, _ = browser_app
    post_observation(base_url)
    template = httpx.get(f"{base_url}/api/observations").json()[0]
    records = []
    for month, count in [("2025-04", 6), ("2026-04", 50), ("2026-05", 5)]:
        for index in range(count):
            records.append({
                **template,
                "id": len(records) + 1,
                "observed_at": f"{month}-01T08:{index:02d}",
            })
    page.route("**/api/observations", lambda route: route.fulfill(json=records))
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(f"{base_url}/observations")
    april = page.locator("#month-records-2026-04")
    old_april = page.locator("#month-records-2025-04")
    may = page.locator("#month-records-2026-05")
    cards = april.locator(".v2-field-card")
    expect(cards).to_have_count(5)
    expect(old_april.locator(".v2-field-card")).to_have_count(5)
    expect(may.locator(".v2-field-card")).to_have_count(5)
    expect(page.locator(".observation-month-toggle")).to_have_count(2)
    expect(page.locator(".v2-book-count strong")).to_have_text("61")
    assert len({round(box["y"]) for box in cards.evaluate_all(
        "items => items.map(item => ({y: item.getBoundingClientRect().y}))"
    )}) == 1
    toggle = page.get_by_role("button", name="共 50 页，点击展开", exact=True)
    expect(toggle).to_have_attribute("aria-expanded", "false")
    page.screenshot(path=str(tmp_path / "monthly-preview.png"), full_page=True)
    toggle.click()
    expect(cards).to_have_count(50)
    expect(old_april.locator(".v2-field-card")).to_have_count(5)
    collapse = page.get_by_role("button", name="共 50 页，点击收起", exact=True)
    expect(collapse).to_have_attribute("aria-expanded", "true")
    cards.last.click()
    detail = page.locator("dialog.observation-detail-dialog[open]")
    expect(detail).to_be_visible()
    page.keyboard.press("Escape")
    expect(cards).to_have_count(50)
    collapse.click()
    expect(cards).to_have_count(5)
    page.get_by_role("button", name="共 6 页，点击展开", exact=True).click()
    expect(old_april.locator(".v2-field-card")).to_have_count(6)
    expect(cards).to_have_count(5)
    toggle.click()
    page.get_by_label("装订顺序", exact=True).select_option("desc")
    expect(cards).to_have_count(5)
    expect(cards.first.locator("time")).to_have_attribute("datetime", "2026-04-01T08:49")
    expect(old_april.locator(".v2-field-card")).to_have_count(5)
    page.get_by_label("年份", exact=True).select_option("2026")
    expect(page.locator(".v2-month-section")).to_have_count(2)
    expect(page.locator(".v2-book-count strong")).to_have_text("55/61")
    page.get_by_label("月份", exact=True).select_option("05")
    expect(page.locator(".v2-month-section")).to_have_count(1)
    expect(page.locator(".observation-month-toggle")).to_have_count(0)
    expect(may.locator(".v2-field-card")).to_have_count(5)
