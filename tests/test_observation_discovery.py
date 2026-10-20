import httpx
from playwright.sync_api import expect
from test_browser_flows import browser_app as browser_app
from test_browser_flows import post_observation


def test_discovery_stamp_uses_full_history_and_seven_digit_numbers(browser_app, tmp_path):
    page, base_url, _ = browser_app
    post_observation(base_url)
    template = httpx.get(f"{base_url}/api/observations").json()[0]
    original = template["species_entries"][0]
    second = {**original, "species_id": 999, "species_name": "喜鹊", "is_primary": False}
    records = [
        {**template, "id": record_id, "observed_at": f"2026-08-{day:02d}T08:00",
         "species_entries": entries, "species_count": len(entries)}
        for record_id, day, entries in [
            (30, 1, [original]), (10, 2, [original]), (20, 1, [original]),
            (40, 3, [original, second]), (10000, 4, [second]),
        ]
    ]
    page.route("**/api/observations", lambda route: route.fulfill(json=records))
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(f"{base_url}/observations")
    cards = page.locator(".v2-field-card")
    stamps = page.locator(".observation-discovery-stamp")
    expect(cards).to_have_count(5)
    expect(stamps).to_have_count(2)
    expect(cards.filter(has_text="#0000020").get_by_alt_text("新发现")).to_have_count(1)
    expect(cards.filter(has_text="#0000040").get_by_alt_text("新发现")).to_have_count(1)
    expect(cards.filter(has_text="#0010000")).to_have_count(1)
    page.get_by_label("装订顺序", exact=True).select_option("desc")
    expect(stamps).to_have_count(2)
    for width in [1920, 1366, 760]:
        page.set_viewport_size({"width": width, "height": 1080})
        for stamp in stamps.all():
            stamp.scroll_into_view_if_needed()
            page.wait_for_function(
                "[...document.querySelectorAll('.observation-discovery-stamp')]"
                ".every(img => img.complete && img.naturalWidth > 0)"
            )
            box = stamp.bounding_box()
            photo = stamp.locator("..").bounding_box()
            card = stamp.locator("xpath=../..")
            text = card.locator(".v2-field-copy").bounding_box()
            number = card.locator("i").bounding_box()
            assert box["y"] >= photo["y"]
            assert box["y"] + box["height"] <= text["y"]
            assert box["x"] >= number["x"] + number["width"]
            assert box["x"] + box["width"] <= photo["x"] + photo["width"]
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.screenshot(path=str(tmp_path / "discovery-stamps.png"), full_page=True)

    # A later import of an older encounter becomes the first for both species.
    records.append({**template, "id": 60, "observed_at": "2026-07-01T08:00",
                    "species_entries": [original, second], "species_count": 2})
    page.reload()
    expect(stamps).to_have_count(1)
    expect(cards.filter(has_text="#0000060").get_by_alt_text("新发现")).to_have_count(1)
    page.get_by_label("月份", exact=True).select_option("08")
    expect(cards).to_have_count(5)
    expect(stamps).to_have_count(0)

    records.pop()
    page.reload()
    expect(stamps).to_have_count(2)
