(() => {
  const byId = (id) => document.getElementById(id);
  const labels = {
    urban_park: "城市公园", campus: "校园", wetland: "湿地", forest: "森林",
    grassland: "草原", nature_reserve: "自然保护区", reservoir: "水库",
    farmland: "农田", coast: "海岸", other: "其他",
  };
  let locations = [];
  const map = L.map("region-overview-map", { zoomControl: true }).setView([35, 105], 4);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  const markers = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 55 });
  map.addLayer(markers);

  function filteredLocations() {
    const query = byId("map-location-search").value.trim().toLocaleLowerCase();
    const type = byId("map-location-type").value;
    return locations.filter((item) => `${item.name} ${item.city || ""} ${item.district || ""} ${item.admin1_name}`.toLocaleLowerCase().includes(query) && (!type || item.location_type === type));
  }

  function render({ fit = false } = {}) {
    const filtered = filteredLocations(); markers.clearLayers();
    for (const item of filtered) {
      const marker = L.marker([item.center_latitude, item.center_longitude]);
      marker.bindPopup(`<strong>${Yuhen.escapeHtml(item.name)}</strong><br>${Yuhen.escapeHtml(labels[item.location_type] || item.location_type)} · ${item.species_count} 种 · ${item.observation_count} 笔记录<br><a href="/locations?location=${item.id}">打开区域档案</a>`);
      markers.addLayer(marker);
    }
    byId("map-location-count").textContent = filtered.length;
    byId("map-location-list").innerHTML = filtered.map((item) => `<button type="button" data-map-location="${item.id}"><strong>${Yuhen.escapeHtml(item.name)}</strong><span>${Yuhen.escapeHtml(item.admin1_name)} · ${item.species_count} 种</span></button>`).join("") || "<p>没有符合条件的区域。</p>";
    byId("map-status").textContent = filtered.length ? `地图显示 ${filtered.length} 处区域档案。` : "没有符合条件的地图点位。";
    if (fit && filtered.length) map.fitBounds(markers.getBounds(), { padding: [35, 35], maxZoom: 13 });
  }

  byId("map-location-search").addEventListener("input", () => render());
  byId("map-location-type").addEventListener("change", () => render({ fit: true }));
  byId("map-location-reset").addEventListener("click", () => { byId("map-location-search").value = ""; byId("map-location-type").value = ""; render({ fit: true }); });
  byId("map-location-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-map-location]"); if (!button) return;
    const item = locations.find((entry) => entry.id === Number(button.dataset.mapLocation));
    if (item) map.setView([item.center_latitude, item.center_longitude], 13);
  });

  Yuhen.api("/api/locations").then((items) => {
    locations = items;
    const types = [...new Set(items.map((item) => item.location_type))].sort();
    byId("map-location-type").innerHTML += types.map((type) => `<option value="${type}">${Yuhen.escapeHtml(labels[type] || type)}</option>`).join("");
    render({ fit: true });
  }).catch((error) => { byId("map-status").textContent = error.message; });
})();
