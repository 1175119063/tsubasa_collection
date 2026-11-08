import json

import httpx
from playwright.sync_api import expect


def wait_for_taxonomy_idle(page) -> None:
    page.wait_for_function(
        """() => document.querySelector('[data-taxonomy-child-track]')
            ?.getAttribute('data-taxonomy-motion') === 'idle'"""
    )


def rectangles_overlap(first: dict, second: dict) -> bool:
    return not (
        first["x"] + first["width"] <= second["x"]
        or second["x"] + second["width"] <= first["x"]
        or first["y"] + first["height"] <= second["y"]
        or second["y"] + second["height"] <= first["y"]
    )


def test_home_sections_fill_the_viewport(browser_app):
    page, base_url, _data_dir = browser_app
    page.set_viewport_size({"width": 1800, "height": 900})
    page.goto(f"{base_url}/")
    page.locator(".v2-camp-hero").wait_for(state="visible")

    viewport_width = page.evaluate("window.innerWidth")
    for selector in (
        ".v2-home",
        ".v2-camp-hero",
        ".v2-camp-board",
        ".v2-latest-section",
        ".v2-api-section",
    ):
        box = page.locator(selector).bounding_box()
        assert box is not None
        assert abs(box["x"]) <= 1
        assert abs(box["width"] - viewport_width) <= 1


def test_tianditu_is_used_as_primary_map_with_browser_key(browser_app, jpeg_bytes):
    page, base_url, _data_dir = browser_app
    page.goto(f"{base_url}/")
    page.locator(".v2-api-manage").click()
    dialog = page.locator("dialog.v2-api-dialog[open]")
    dialog.get_by_label("浏览器端 Key（tk）").fill("browser-map-key")
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/integrations/tianditu") and response.request.method == "PUT"
        )
    ) as save_response:
        dialog.get_by_role("button", name="保存底图配置").click()
    assert save_response.value.status == 200
    dialog.get_by_text("天地图浏览器端 Key 已保存。", exact=True).wait_for()
    dialog.get_by_role("button", name="关闭").click()
    tile_urls: list[str] = []

    def fulfill_tile(route) -> None:
        tile_urls.append(route.request.url)
        route.fulfill(body=jpeg_bytes(), content_type="image/jpeg")

    page.route("https://t*.tianditu.gov.cn/**", fulfill_tile)
    page.goto(f"{base_url}/map")
    page.get_by_text("天地图底图已加载", exact=False).wait_for(timeout=90000)

    assert any("/vec_w/wmts" in url for url in tile_urls)
    assert any("/cva_w/wmts" in url for url in tile_urls)
    assert all("tk=browser-map-key" in url for url in tile_urls)
    assert page.locator(".leaflet-control-layers").count() == 1


def test_tianditu_tile_failure_falls_back_to_openstreetmap(browser_app, jpeg_bytes):
    page, base_url, _data_dir = browser_app
    response = httpx.put(
        f"{base_url}/api/integrations/tianditu",
        json={"api_key": "unavailable-map-key", "clear_api_key": False},
    )
    response.raise_for_status()
    osm_urls: list[str] = []
    page.route("https://t*.tianditu.gov.cn/**", lambda route: route.abort())

    def fulfill_osm(route) -> None:
        osm_urls.append(route.request.url)
        route.fulfill(body=jpeg_bytes(), content_type="image/jpeg")

    page.route("https://tile.openstreetmap.org/**", fulfill_osm)
    page.goto(f"{base_url}/map")
    page.get_by_text("已切换到 OpenStreetMap 备用底图", exact=False).wait_for()

    assert osm_urls


def _post_location_at(base_url: str, name: str, latitude: float, longitude: float) -> dict:
    response = httpx.post(
        f"{base_url}/api/locations",
        json={
            "name": name,
            "location_type": "urban_park",
            "country_code": "CN",
            "country_name": "China",
            "admin1_code": "CN-ZJ",
            "admin1_name": "Zhejiang",
            "city": "Hangzhou",
            "district": None,
            "center_latitude": latitude,
            "center_longitude": longitude,
            "coordinate_system": "wgs84",
            "radius_meters": 3000,
            "notes": None,
            "link_matching_records": False,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def test_map_fits_every_location_on_first_load(browser_app, jpeg_bytes):
    page, base_url, _data_dir = browser_app
    page.set_viewport_size({"width": 1440, "height": 900})
    _post_location_at(base_url, "北京奥林匹克森林公园", 40.0184, 116.3831)
    _post_location_at(base_url, "济南大明湖", 36.6777, 117.0390)
    tile_zooms: list[int] = []

    def fulfill_tile(route) -> None:
        tile_zooms.append(int(route.request.url.rsplit("/", 3)[1]))
        route.fulfill(body=jpeg_bytes(), content_type="image/jpeg")

    page.route("https://tile.openstreetmap.org/**", fulfill_tile)
    page.goto(f"{base_url}/map")
    page.locator(".leaflet-marker-icon, .marker-cluster").first.wait_for(timeout=30000)
    page.wait_for_timeout(600)

    assert tile_zooms, "地图没有请求任何底图瓦片"
    assert min(tile_zooms) >= 7, (
        "地图先在未自适应的缩放下渲染了底图，说明首屏用的是占位视图而不是自适应结果："
        f"{sorted(set(tile_zooms))}"
    )


def test_map_markers_render_real_pin_images(browser_app, jpeg_bytes):
    page, base_url, _data_dir = browser_app
    page.set_viewport_size({"width": 1440, "height": 900})
    _post_location_at(base_url, "杭州西湖", 30.2741, 120.1551)
    _post_location_at(base_url, "哈尔滨太阳岛", 45.7500, 126.6500)
    not_found: list[str] = []
    page.on(
        "response",
        lambda response: not_found.append(response.url) if response.status == 404 else None,
    )
    page.route(
        "https://tile.openstreetmap.org/**",
        lambda route: route.fulfill(body=jpeg_bytes(), content_type="image/jpeg"),
    )
    page.goto(f"{base_url}/map")
    page.locator(".leaflet-marker-icon").first.wait_for(timeout=30000)
    page.wait_for_timeout(800)

    broken = page.evaluate(
        """() => Array.from(document.querySelectorAll('.leaflet-marker-icon')).map((element) => {
            if (element.tagName === 'IMG') {
                return element.complete && element.naturalWidth > 0 ? null : 'img-broken';
            }
            const background = getComputedStyle(element).backgroundImage;
            return background && background !== 'none' ? null : 'no-background';
        }).filter(Boolean)"""
    )
    assert broken == [], f"地图标记没有加载出真实图标：{broken}"
    assert not [url for url in not_found if "marker" in url], f"标记图标请求 404：{not_found}"


def test_openstreetmap_tile_failure_is_reported_to_the_reader(browser_app):
    page, base_url, _data_dir = browser_app
    page.route("https://tile.openstreetmap.org/**", lambda route: route.abort())
    page.goto(f"{base_url}/map")

    page.get_by_text("OpenStreetMap 底图瓦片加载失败", exact=False).wait_for(timeout=30000)


def test_personal_taxonomy_navigation_url_and_species_actions(browser_app, post_observation):
    page, base_url, _data_dir = browser_app
    created = post_observation(base_url)
    page.set_viewport_size({"width": 1600, "height": 1000})
    page.goto(f"{base_url}/dex")

    page.locator("[data-taxonomy-switch]").click()
    browser = page.locator("[data-taxonomy-browser]")
    browser.wait_for(state="visible")
    assert "PERSONAL TAXON" not in browser.inner_text()
    assert page.locator(".v2-taxonomy-node-copy small").count() == 0
    assert "view=taxonomy" in page.url
    assert "rank=class" in page.url
    assert page.locator('[data-taxonomy-current][data-rank="class"]').count() == 1
    assert "脊索动物门" in page.locator("[data-taxonomy-phylum]").inner_text()
    assert page.locator("[data-taxonomy-phylum] button").count() == 0
    assert page.locator(".is-taxonomy-view .v2-dex-header").count() == 0
    for width, height in [(1920, 1080), (1440, 900), (1366, 768)]:
        page.set_viewport_size({"width": width, "height": height})
        summary = page.locator(".v2-taxonomy-summary").bounding_box()
        tree = page.locator("[data-taxonomy-child-track]").bounding_box()
        assert summary and tree
        assert tree["y"] >= 92
        assert tree["y"] + tree["height"] <= summary["y"] + 1
        assert summary["y"] + summary["height"] <= height
    page.set_viewport_size({"width": 1600, "height": 1000})

    current_box = page.locator("[data-taxonomy-current]").bounding_box()
    child_box = page.locator("[data-taxonomy-child]").first.bounding_box()
    assert current_box and child_box and child_box["y"] < current_box["y"]
    stage_box = page.locator("[data-taxonomy-child-track]").bounding_box()
    child_avatar_box = page.locator(
        "[data-taxonomy-child] [data-taxonomy-avatar]"
    ).first.bounding_box()
    assert stage_box and child_avatar_box
    assert child_avatar_box["y"] - stage_box["y"] >= 24
    assert abs(child_avatar_box["width"] - child_avatar_box["height"]) <= 1

    scroll_before = page.evaluate("""() => {
        window.scrollTo(0, Math.min(420, document.documentElement.scrollHeight - innerHeight));
        return window.scrollY;
    }""")
    assert scroll_before > 0
    page.locator('[data-taxonomy-child][data-rank="order"]').first.evaluate(
        "element => element.click()"
    )
    page.locator('[data-taxonomy-current][data-rank="order"]').wait_for()
    page.wait_for_url("**rank=order**")
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    assert abs(page.evaluate("window.scrollY") - scroll_before) <= 2

    for rank in ("family", "genus", "species"):
        page.locator(f'[data-taxonomy-child][data-rank="{rank}"]').first.click()
        page.locator(f'[data-taxonomy-current][data-rank="{rank}"]').wait_for()
        assert f"rank={rank}" in page.url

    catalog_marker = page.locator("[data-taxonomy-current] .v2-taxonomy-node-copy small")
    assert catalog_marker.inner_text() == created["catalog_number"]

    assert page.locator("[data-taxonomy-breadcrumb]").count() == 0
    assert page.get_by_text("已经抵达分类树末端", exact=True).count() == 0
    assert page.locator(".taxonomy-empty-slot .taxonomy-placeholder").count() == 5
    current_box = page.locator("[data-taxonomy-current]").bounding_box()
    parent_box = page.locator("[data-taxonomy-parent]").bounding_box()
    stage_box = page.locator("[data-taxonomy-child-track]").bounding_box()
    assert current_box and parent_box and stage_box
    current_avatar_box = page.locator(
        "[data-taxonomy-current] [data-taxonomy-avatar]"
    ).bounding_box()
    current_copy_box = page.locator("[data-taxonomy-current] .v2-taxonomy-node-copy").bounding_box()
    assert current_avatar_box and current_copy_box
    parent_avatar_box = page.locator("[data-taxonomy-parent] [data-taxonomy-avatar]").bounding_box()
    assert parent_avatar_box
    avatar_center_x = current_avatar_box["x"] + current_avatar_box["width"] / 2
    avatar_center_y = current_avatar_box["y"] + current_avatar_box["height"] / 2
    parent_center_x = parent_avatar_box["x"] + parent_avatar_box["width"] / 2
    assert abs(avatar_center_x - (stage_box["x"] + stage_box["width"] / 2)) <= 1
    assert abs(avatar_center_y - (stage_box["y"] + stage_box["height"] * 0.568)) <= 1
    assert abs(parent_center_x - avatar_center_x) <= 1
    assert parent_avatar_box["y"] > current_avatar_box["y"] + current_avatar_box["height"]
    assert current_copy_box["x"] >= current_avatar_box["x"] + current_avatar_box["width"] + 12
    assert not rectangles_overlap(current_box, parent_box)
    parent_line = page.locator("[data-taxonomy-parent-line]")
    parent_x1 = float(parent_line.get_attribute("x1"))
    parent_x2 = float(parent_line.get_attribute("x2"))
    parent_y1 = float(parent_line.get_attribute("y1"))
    parent_y2 = float(parent_line.get_attribute("y2"))
    assert abs(parent_x1 - parent_x2) <= 0.01
    assert abs(parent_y2 - parent_y1) >= 15

    page.locator("[data-taxonomy-parent]").click()
    page.locator('[data-taxonomy-current][data-rank="genus"]').wait_for()
    page.go_back()
    page.locator('[data-taxonomy-current][data-rank="species"]').wait_for()
    page.reload()
    page.locator('[data-taxonomy-current][data-rank="species"]').wait_for()
    assert f"node={created['species_id']}" in page.url

    page.get_by_role("button", name="打开物种档案").click()
    dossier = page.locator("dialog.v2-dossier[open]")
    dossier.wait_for(state="visible")
    dossier.locator(".v2-dossier-hero").wait_for(state="visible")
    assert "白腰文鸟" in dossier.inner_text()
    dossier.get_by_role("button", name="关闭").click()
    page.get_by_role("button", name="查看田野记录").click()
    page.wait_for_url("**/observations?species=*")
    page.locator(".v2-field-card").wait_for()
    assert page.locator(".v2-field-card").count() == 1

    page.goto(f"{base_url}/dex?view=taxonomy&rank=species&node={created['species_id']}")
    page.locator('[data-taxonomy-current][data-rank="species"]').wait_for()
    page.locator("[data-taxonomy-switch]").click()
    page.locator(".v2-species-grid").wait_for()
    assert "view=taxonomy" not in page.url


def test_personal_taxonomy_carousel_and_first_portrait(
    browser_app, observation_payload, post_observation
):
    page, base_url, _data_dir = browser_app
    for index, suffix in enumerate("甲乙丙丁戊己"):
        payload = observation_payload()
        payload["new_species"]["family"] = {
            "chinese_name": "测试科",
            "scientific_name": "Testidae",
        }
        payload["new_species"]["genus"] = {
            "chinese_name": f"测试{suffix}属",
            "scientific_name": f"Testgenus{index + 1}",
        }
        payload["new_species"]["chinese_name"] = f"测试鸟{suffix}"
        payload["new_species"]["scientific_name"] = f"Testgenus{index + 1} avis"
        payload["observed_at"] = f"2026-08-15T08:{30 + index:02d}"
        post_observation(
            base_url,
            payload,
            color=(70 + index * 20, 95 + index * 10, 80 + index * 12),
        )

    page.set_viewport_size({"width": 1600, "height": 1000})
    page.goto(f"{base_url}/dex?view=taxonomy&rank=class&node=aves")
    page.locator("[data-taxonomy-browser]").wait_for()
    page.locator('[data-taxonomy-child][data-rank="order"]').click()
    page.locator('[data-taxonomy-child][data-rank="family"]').click()
    page.locator('[data-taxonomy-current][data-rank="family"]').wait_for()

    children = page.locator("[data-taxonomy-child]")
    assert children.count() == 5
    node_metrics = page.locator("[data-taxonomy-browser] .v2-taxonomy-node").evaluate_all(
        """nodes => nodes.map(node => {
            const avatar = node.querySelector('[data-taxonomy-avatar]');
            const chineseName = node.querySelector('.v2-taxonomy-node-copy strong');
            const scientificName = node.querySelector('.v2-taxonomy-node-copy em');
            return {
                avatarWidth: getComputedStyle(avatar).width,
                avatarHeight: getComputedStyle(avatar).height,
                chineseSize: getComputedStyle(chineseName).fontSize,
                scientificSize: getComputedStyle(scientificName).fontSize,
            };
        })"""
    )
    assert len(node_metrics) == 7
    assert len({metric["avatarWidth"] for metric in node_metrics}) == 1
    assert len({metric["avatarHeight"] for metric in node_metrics}) == 1
    assert len({metric["chineseSize"] for metric in node_metrics}) == 1
    assert len({metric["scientificSize"] for metric in node_metrics}) == 1
    stage_box = page.locator("[data-taxonomy-child-track]").bounding_box()
    assert stage_box
    # Portraits must occupy the five sockets in the supplied illustration.
    sockets = [(18.15, 40.95), (31.05, 24.4), (50, 16.1), (68.95, 24.4), (81.85, 40.95)]
    for index, (x, y) in enumerate(sockets):
        avatar = children.nth(index).locator("[data-taxonomy-avatar]").bounding_box()
        assert avatar
        expected_x = stage_box["x"] + stage_box["width"] * x / 100
        assert abs(avatar["x"] + avatar["width"] / 2 - expected_x) < 1
        expected_y = stage_box["y"] + stage_box["height"] * y / 100
        assert abs(avatar["y"] + avatar["height"] / 2 - expected_y) < 1
    child_boxes = [children.nth(index).bounding_box() for index in range(5)]
    assert all(child_boxes)
    for child_box in child_boxes:
        assert child_box
        assert child_box["x"] >= stage_box["x"]
        assert child_box["x"] + child_box["width"] <= stage_box["x"] + stage_box["width"]
    for index, first_box in enumerate(child_boxes):
        for second_box in child_boxes[index + 1 :]:
            assert first_box and second_box
            assert not rectangles_overlap(first_box, second_box)
    first_window = children.evaluate_all(
        "nodes => nodes.map(node => node.getAttribute('data-node-id'))"
    )
    assert "01—05 / 06" in page.locator(".v2-taxonomy-context").inner_text()

    current_portraits = page.locator("[data-taxonomy-current] [data-taxonomy-avatar] img")
    assert current_portraits.count() == 1
    species_response = httpx.get(f"{base_url}/api/species")
    species_response.raise_for_status()
    first_species = min(species_response.json(), key=lambda item: item["id"])
    assert current_portraits.get_attribute("src") == first_species["cover_url"]

    track = page.locator("[data-taxonomy-child-track]")
    track.focus()
    track.press("ArrowRight")
    assert track.get_attribute("data-taxonomy-motion") == "forward"
    page.wait_for_function(
        """() => document.querySelector('[data-taxonomy-window]')
            ?.getAnimations({ subtree: true })
            .some(animation => animation.playState === 'running'
                && Number(animation.effect?.getTiming().duration || 0) >= 300)"""
    )
    wait_for_taxonomy_idle(page)
    second_window = children.evaluate_all(
        "nodes => nodes.map(node => node.getAttribute('data-node-id'))"
    )
    assert first_window != second_window

    track.press("ArrowLeft")
    assert track.get_attribute("data-taxonomy-motion") == "backward"
    wait_for_taxonomy_idle(page)
    assert (
        children.evaluate_all("nodes => nodes.map(node => node.getAttribute('data-node-id'))")
        == first_window
    )
    bounds = track.bounding_box()
    assert bounds
    track.evaluate(
        """element => {
            const bounds = element.getBoundingClientRect();
            for (const deltaY of [10, 10, 10, 10, 90]) {
                element.dispatchEvent(new WheelEvent('wheel', {
                    bubbles: true,
                    cancelable: true,
                    clientX: bounds.left + bounds.width / 2,
                    clientY: bounds.top + 40,
                    deltaY,
                }));
            }
        }"""
    )
    assert track.get_attribute("data-taxonomy-motion") == "forward"
    assert track.get_attribute("data-taxonomy-window-start") == "1"
    wait_for_taxonomy_idle(page)
    assert (
        children.evaluate_all("nodes => nodes.map(node => node.getAttribute('data-node-id'))")
        != first_window
    )


def test_assistant_previews_then_fills_new_species_taxonomy(browser_app, tmp_path, jpeg_bytes):
    page, base_url, _data_dir = browser_app
    page.route(
        "**/api/assistant/status",
        lambda route: route.fulfill(json={"enabled": True, "available": True, "message": "ready"}),
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
    dialog = page.locator("dialog.batch-dialog[open]")
    photo = tmp_path / "assistant.jpg"
    photo.write_bytes(jpeg_bytes())
    dialog.get_by_label("批量选择照片", exact=True).set_input_files(str(photo))
    dialog.locator("[data-new-species]").click()
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


def test_browser_can_create_observation_with_existing_species(
    browser_app, tmp_path, jpeg_bytes, post_observation
):
    page, base_url, _data_dir = browser_app
    original = post_observation(base_url)
    photo_path = tmp_path / "vue-observation.jpg"
    photo_path.write_bytes(jpeg_bytes((92, 114, 78)))

    page.goto(f"{base_url}/observations?new=1")
    dialog = page.locator("dialog.batch-dialog[open]")
    dialog.wait_for(state="visible")
    form = dialog.locator("form")
    dialog.get_by_label("批量选择照片", exact=True).set_input_files(str(photo_path))
    form.locator("fieldset").first.locator("select").first.select_option(
        str(original["species_id"])
    )
    location = form.locator("fieldset").nth(1)
    location.get_by_label("拍摄时间", exact=True).fill("2026-08-26T07:15")
    location.get_by_label("纬度", exact=True).fill("30.275")
    location.get_by_label("经度", exact=True).fill("120.156")
    location.get_by_label("一级行政区代码", exact=True).fill("CN-ZJ")
    location.get_by_label("一级行政区名称", exact=True).fill("Zhejiang")
    location.get_by_label("具体地点", exact=True).fill("West Lake")

    season = location.get_by_label("季节", exact=True)
    assert season.input_value() == ""
    assert dialog.get_by_role("button", name="保存就绪照片（0）").is_disabled()
    assert season.evaluate("element => element.validity.valueMissing")
    assert len(httpx.get(f"{base_url}/api/observations").json()) == 1
    season.select_option("summer")

    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/observations") and response.request.method == "POST"
        )
    ) as response_info:
        dialog.get_by_role("button", name="保存就绪照片（1）").click()
    assert response_info.value.status == 201
    dialog.locator('.batch-item[data-state="saved"]').wait_for(state="visible")
    dialog.get_by_role("button", name="关闭登记新发现").click()
    page.locator(".v2-field-card").nth(1).wait_for(state="visible")
    assert len(httpx.get(f"{base_url}/api/observations").json()) == 2


def test_browser_can_view_and_extend_multi_photo_observation(
    browser_app, tmp_path, jpeg_bytes, observation_payload
):
    page, base_url, _data_dir = browser_app
    third_photo = tmp_path / "encounter-third.jpg"
    third_photo.write_bytes(jpeg_bytes((70, 95, 125)))
    payload = observation_payload()
    payload["observed_at"] = "2026-08-26T07:15"
    payload["photos"] = [
        {"observed_at": timestamp, "includes_primary": True, "is_cover": index == 0}
        for index, timestamp in enumerate(["2026-08-26T07:15", "2026-08-26T07:17"])
    ]
    created = httpx.post(
        f"{base_url}/api/observations",
        data={"payload": json.dumps(payload, ensure_ascii=False)},
        files=[
            ("photo", ("first.jpg", jpeg_bytes((92, 114, 78)), "image/jpeg")),
            ("additional_photos", ("second.jpg", jpeg_bytes((110, 90, 72)), "image/jpeg")),
        ],
    )
    created.raise_for_status()
    page.goto(f"{base_url}/observations?observation={created.json()['observation_id']}")
    detail = page.locator("dialog.observation-detail-dialog[open]")
    detail.get_by_role("button", name="下一张照片").wait_for(state="visible")
    detail.get_by_role("button", name="下一张照片").click()
    detail.get_by_text("2 / 2", exact=True).wait_for(state="visible")

    detail.get_by_role("button", name="修改记录").click()
    editor = page.locator("dialog.observation-entry-dialog[open]")
    editor.locator(".observation-photo-manager-list article").nth(1).wait_for()
    editor.get_by_label("选择 JPEG/JPG").set_input_files(str(third_photo))
    editor.locator(".observation-photo-add").get_by_label("拍摄时间").fill("2026-08-26T07:20")
    add_photo = editor.get_by_role("button", name="保存这张补充照片")
    expect(add_photo).to_be_enabled(timeout=90000)
    with page.expect_response(
        lambda response: "/photos" in response.url and response.request.method == "POST"
    ) as add_response:
        add_photo.click()
    assert add_response.value.status == 201
    editor.get_by_text("3 / 20 张", exact=True).wait_for()
    record = max(
        httpx.get(f"{base_url}/api/observations").json(),
        key=lambda item: item["id"],
    )
    assert record["photo_count"] == 3
    assert [item["observed_at"] for item in record["photos"]] == [
        "2026-08-26T07:15",
        "2026-08-26T07:17",
        "2026-08-26T07:20",
    ]


def test_species_dossier_identity_and_ecology_layout(browser_app, post_observation):
    page, base_url, _data_dir = browser_app
    created = post_observation(base_url)
    page.goto(f"{base_url}/dex?species={created['species_id']}")
    dossier = page.locator("dialog.v2-dossier[open]")
    dossier.wait_for(state="visible")
    assert dossier.get_by_text("档案完整度", exact=False).count() == 0
    for width, height in [(1366, 768), (1440, 900), (1920, 1080)]:
        page.set_viewport_size({"width": width, "height": height})
        name = dossier.locator(".dossier-species-name").bounding_box()
        encounter = dossier.locator(".dossier-first-encounter").bounding_box()
        ecology = dossier.locator(".v2-dossier-title .v2-ecology-panel").bounding_box()
        assert name and encounter and ecology
        assert encounter["x"] >= name["x"] + name["width"]
        assert ecology["y"] >= encounter["y"] + encounter["height"]
    dossier.locator(".dossier-first-encounter").click()
    page.wait_for_url("**/observations?observation=*")
    assert f"observation={created['observation_id']}" in page.url



def test_browser_can_complete_species_profile_from_online_sources(
    browser_app, post_observation
):
    page, base_url, _data_dir = browser_app
    created = post_observation(base_url)
    species_id = created["species_id"]
    page.goto(f"{base_url}/dex?species={species_id}")
    dossier = page.locator("dialog.v2-dossier[open]")
    dossier.wait_for(state="visible")
    dossier.get_by_role("button", name="修改图鉴").click()

    profile = page.locator("dialog.profile-dialog[open]")
    profile.wait_for(state="visible")
    notes = profile.get_by_label("物种简介")
    notes.fill("我在校园里见过它。")
    saved_profile_requests: list[str] = []
    page.on(
        "request",
        lambda request: (
            saved_profile_requests.append(request.url)
            if request.method == "PUT" and "/profile" in request.url
            else None
        ),
    )
    page.route(
        "**/api/assistant/species-profile",
        lambda route: route.fulfill(
            status=200,
            json={
                "introduction": "灰喜鹊常成群活动；我在校园里见过它在树上跳跃。",
                "warnings": [],
                "sources": [
                    {"title": "iNaturalist", "url": "https://www.inaturalist.org/taxa/1"}
                ],
            },
        ),
    )
    with page.expect_request("**/api/assistant/species-profile") as request_info:
        profile.get_by_role("button", name="飞羽精灵补全").click()
    payload = json.loads(request_info.value.post_data or "{}")
    assert payload["introduction"] == "我在校园里见过它。"
    assert payload["scientific_name"]
    expect(notes).to_have_value("灰喜鹊常成群活动；我在校园里见过它在树上跳跃。")
    assert saved_profile_requests == []
    assert profile.is_visible()


def test_browser_keeps_species_profile_when_completion_fails(
    browser_app, post_observation
):
    page, base_url, _data_dir = browser_app
    created = post_observation(base_url)
    species_id = created["species_id"]
    page.goto(f"{base_url}/dex?species={species_id}")
    dossier = page.locator("dialog.v2-dossier[open]")
    dossier.wait_for(state="visible")
    dossier.get_by_role("button", name="修改图鉴").click()

    profile = page.locator("dialog.profile-dialog[open]")
    profile.wait_for(state="visible")
    notes = profile.get_by_label("物种简介")
    notes.fill("原有观察记录。")
    page.route(
        "**/api/assistant/species-profile",
        lambda route: route.fulfill(
            status=503,
            json={"detail": "AI 整理暂时不可用：模型离线。；简介没有修改。"},
        ),
    )
    with page.expect_request("**/api/assistant/species-profile"):
        profile.get_by_role("button", name="飞羽精灵补全").click()
    expect(notes).to_have_value("原有观察记录。")
    expect(profile.locator(".profile-intro-status")).to_contain_text("模型离线")
    assert profile.is_visible()


def test_browser_can_edit_species_profile_and_open_audio_form(
    browser_app, tmp_path, post_observation
):
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
        lambda response: (
            response.url.endswith(f"/api/species/{species_id}/profile")
            and response.request.method == "PUT"
        )
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
        lambda response: (
            response.url.endswith(f"/api/species/{species_id}/audio")
            and response.request.method == "POST"
        )
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
        lambda response: (
            response.url.endswith("/api/locations") and response.request.method == "POST"
        )
    ) as response_info:
        form.locator('button[type="submit"]').click()
    assert response_info.value.status == 201
    page.locator("dialog.v2-archive-dialog[open]").wait_for(state="visible")
    page.wait_for_url("**/locations?location=*")
    assert "new=1" not in page.url
    assert len(httpx.get(f"{base_url}/api/locations").json()) == 1


def test_browser_can_create_trip_and_open_saved_detail(browser_app, post_location):
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
        lambda response: response.url.endswith("/api/trips") and response.request.method == "POST"
    ) as response_info:
        form.locator('button[type="submit"]').click()
    assert response_info.value.status == 201
    page.locator("dialog.v2-archive-dialog[open]").wait_for(state="visible")
    page.wait_for_url("**/trips?trip=*")
    assert "new=1" not in page.url
    assert len(httpx.get(f"{base_url}/api/trips").json()) == 1


def test_browser_can_permanently_delete_observation(browser_app, post_observation):
    page, base_url, _data_dir = browser_app
    post_observation(base_url)
    page.goto(f"{base_url}/observations")
    page.locator(".v2-field-card", has_text="白腰文鸟").click()
    detail = page.locator("dialog.v2-archive-dialog[open]")
    detail.wait_for(state="visible")
    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_response(
        lambda response: (
            "/api/observations/" in response.url and response.request.method == "DELETE"
        )
    ) as response_info:
        detail.get_by_role("button", name="永久删除").click()
    assert response_info.value.status == 200
    page.wait_for_url(f"{base_url}/observations")
    page.get_by_text("从一次相遇开始", exact=True).wait_for(state="visible")
    page.get_by_role("button", name="登记第一笔观察").wait_for(state="visible")
    assert httpx.get(f"{base_url}/api/observations").json() == []


def test_browser_can_restore_complete_backup(browser_app, post_observation):
    page, base_url, data_dir = browser_app
    created = post_observation(base_url)
    page.goto(base_url)
    page.get_by_role("button", name="完整备份资料库").click()
    backup_dialog = page.get_by_role("dialog")
    backup_dialog.wait_for(state="visible")
    with page.expect_response(
        lambda response: response.url.endswith("/api/backups") and response.request.method == "POST"
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


def test_browser_collection_plan_selects_crops_and_previews_evidence(browser_app, post_observation):
    page, base_url, _data_dir = browser_app
    post_observation(base_url)
    page.goto(f"{base_url}/collections?new=1")
    plan_form = page.locator("dialog.collection-form-dialog[open]")
    plan_form.wait_for(state="visible")
    plan_form.get_by_label("计划名称").fill("文鸟观察集")
    plan_form.get_by_label("观察记录简介").fill("比较不同个体形态。")
    plan_form.get_by_text("性别与年龄", exact=True).click()
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/collections") and response.request.method == "POST"
        )
    ) as create_info:
        plan_form.get_by_role("button", name="保存计划").click()
    assert create_info.value.status == 201
    detail = page.locator("dialog.collection-detail-dialog[open]")
    detail.wait_for(state="visible")
    cover_box = page.locator(".collection-plan-cover").first.bounding_box()
    assert cover_box is not None
    assert abs(cover_box["width"] - cover_box["height"]) <= 1
    assert detail.get_by_text("计划中还没有鸟种", exact=True).is_visible()
    detail.get_by_role("button", name="添加鸟种", exact=False).click()
    member_dialog = page.locator("dialog.collection-member-dialog[open]")
    member_dialog.wait_for(state="visible")
    member_dialog.get_by_role("checkbox").check()
    with page.expect_response(
        lambda response: (
            response.url.endswith("/species")
            and "/api/collections/" in response.url
            and response.request.method == "PUT"
        )
    ) as members_info:
        member_dialog.get_by_role("button", name="保存鸟种").click()
    assert members_info.value.status == 200
    first_slot = detail.locator(".collection-slot").first
    species_name = first_slot.locator(".collection-label b")
    assert species_name.inner_text() == "白腰文鸟"
    variant = first_slot.locator(".collection-label i")
    assert variant.inner_text() == "♂"
    assert variant.evaluate("element => getComputedStyle(element).fontStyle") == "italic"
    assert variant.evaluate("element => getComputedStyle(element).color") != (
        species_name.evaluate("element => getComputedStyle(element).color")
    )
    assert species_name.evaluate("element => element.scrollWidth <= element.clientWidth")
    detail.get_by_role("button", name="为 白腰文鸟 ♂ 选择照片凭证").click()
    evidence = page.locator("dialog.collection-evidence-modal[open]")
    evidence.wait_for(state="visible")
    evidence.locator(".collection-evidence-list button").first.click()
    evidence.locator('input[type="range"]').fill("2")
    with page.expect_response(
        lambda response: (
            "/api/collections/" in response.url
            and "/slots/" in response.url
            and response.request.method == "PUT"
        )
    ) as response_info:
        evidence.get_by_role("button", name="保存头像").click()
    assert response_info.value.status == 200

    assert detail.locator(".collection-logo-panel > button").count() == 0
    detail.get_by_role("button", name="修改计划资料", exact=True).click()
    plan_form.wait_for(state="visible")
    radio_sizes = plan_form.locator('.collection-template-grid input[type="radio"]').evaluate_all(
        "elements => elements.map(element => [element.offsetWidth, element.offsetHeight])"
    )
    assert radio_sizes == [[16, 16]] * 4
    plan_form.get_by_role("button", name="设置计划 Logo", exact=True).click()
    logo_dialog = page.locator("dialog.collection-logo-modal[open]")
    logo_dialog.wait_for(state="visible")
    logo_dialog.locator(".collection-logo-candidates button").first.click()
    with page.expect_response(
        lambda response: (
            response.url.endswith("/logo")
            and "/api/collections/" in response.url
            and response.request.method == "PUT"
        )
    ) as logo_info:
        logo_dialog.get_by_role("button", name="保存 Logo").click()
    assert logo_info.value.status == 200
    assert detail.locator(".collection-logo-panel > img").is_visible()
    assert plan_form.get_by_alt_text("当前计划 Logo").is_visible()
    plan_form.get_by_role("button", name="关闭", exact=True).click()
    plan_form.wait_for(state="hidden")

    detail.get_by_role("button", name="查看 白腰文鸟 ♂ 的计划档案").click()
    preview = detail.locator(".collection-preview-panel")
    preview.get_by_role("heading", name="白腰文鸟", exact=True).wait_for(state="visible")
    assert preview.get_by_text("梅花雀科", exact=True).is_visible()
    assert preview.get_by_text("IUCN LC · 无危", exact=True).is_visible()
    assert preview.get_by_text("收集子项 · ♂", exact=True).is_visible()
    assert preview.get_by_role("link", name="查看这笔照片凭证").is_visible()
    preview.get_by_role("textbox").fill("记录它在文鸟专题中的辨识要点。")
    with page.expect_response(
        lambda response: (
            response.url.endswith("/introduction")
            and "/api/collections/" in response.url
            and response.request.method == "PUT"
        )
    ) as introduction_info:
        preview.get_by_role("button", name="保存简介").click()
    assert introduction_info.value.status == 200
    preview.get_by_text("专题简介已保存", exact=True).wait_for(state="visible")


def test_browser_collection_plan_without_subitems_uses_portrait_index(browser_app):
    page, base_url, _data_dir = browser_app
    response = httpx.post(
        f"{base_url}/api/collections",
        json={
            "name": "单幅鸟种收集",
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
