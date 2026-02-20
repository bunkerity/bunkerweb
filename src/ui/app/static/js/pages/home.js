$(function () {
  // Dynamic translation function that always uses the latest i18next state
  const t = (key, options = {}) => {
    if (typeof i18next !== "undefined" && i18next.isInitialized) {
      return i18next.t(key, options);
    }
    return key; // Fallback to key if i18next is not ready
  };

  var headingColor = config.colors.headingColor;
  var legendColor = config.colors.bodyColor;

  var theme = $("#theme").val();

  if (theme === "dark") {
    headingColor = config.colors.white;
    legendColor = config.colors.white;
  }

  // Requests countries map

  const requestsMapData = JSON.parse($("#requests-map-data").text());

  // Initialize the map
  const map = L.map("requests-map", {
    minZoom: 2,
    maxZoom: 4,
    center: [40, 0], // Initial center
    zoom: 2, // Initial zoom level
    maxBounds: [
      [-85, -180], // Southwest corner of the bounding box
      [85, 180], // Northeast corner of the bounding box
    ],
    maxBoundsViscosity: 1.0, // Controls how hard it is to drag out of bounds (1.0 = strict)
  });

  // Add a tile layer (OpenStreetMap)
  const baseUrl = window.location.href.split("/home")[0];
  L.tileLayer(`${baseUrl}/img/tiles/{z}/{x}/{y}.png`, {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  // Control to display country info on hover
  const info = L.control({ position: "topright" });

  info.onAdd = function () {
    this._div = L.DomUtil.create("div", "info"); // Create a div with class "info"
    return this._div;
  };

  // Method to update the control based on feature properties
  info.update = function (props) {
    const blockedCount = props?.blocked ?? 0;
    const blockedCountStr = Number.isFinite(blockedCount)
      ? new Intl.NumberFormat().format(blockedCount)
      : "0";

    this._div.innerHTML = props
      ? `
          <div class="card shadow-none p-2 map-hover-card">
              <div class="card-header p-1 pb-0 border-0">
                  <h5 class="card-title mb-0">${props.ADMIN}</h5>
              </div>
              <div class="card-body p-1 pt-1">
                  <p class="card-text">${t(
                    "dashboard.map.blocked_requests",
                  )}: <strong>${blockedCountStr}</strong></p>
              </div>
          </div>
      `
      : `
          <div class="alert alert-primary map-hover-empty" role="alert">
              ${t("dashboard.map.hover_info")}
          </div>
      `;
  };

  info.addTo(map);

  // Function to adjust lightness of a base color
  function adjustColor(hex, percent) {
    let num = parseInt(hex.slice(1), 16),
      amt = Math.round(2.55 * percent),
      R = (num >> 16) + amt,
      G = ((num >> 8) & 0x00ff) + amt,
      B = (num & 0x0000ff) + amt;

    return (
      "#" +
      (
        0x1000000 +
        (R < 255 ? (R < 1 ? 0 : R) : 255) * 0x10000 +
        (G < 255 ? (G < 1 ? 0 : G) : 255) * 0x100 +
        (B < 255 ? (B < 1 ? 0 : B) : 255)
      )
        .toString(16)
        .slice(1)
    );
  }

  const baseMapColor = "#0b354a";
  const noDataColor = "#6a6a6a";

  const blockedValues = Object.values(requestsMapData)
    .map((item) => parseInt(item?.blocked ?? 0, 10))
    .filter((value) => Number.isFinite(value) && value > 0);

  function niceStep(value) {
    const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
    const residual = value / magnitude;
    if (residual <= 1) return 1 * magnitude;
    if (residual <= 2) return 2 * magnitude;
    if (residual <= 5) return 5 * magnitude;
    return 10 * magnitude;
  }

  function buildLegendGrades(values) {
    if (!values.length) {
      return [0, 1];
    }

    const maxValue = Math.max(...values);
    const targetBuckets = 6;
    const step = Math.max(1, Math.round(niceStep(maxValue / targetBuckets)));
    const grades = [0];

    for (let current = step; current < maxValue; current += step) {
      grades.push(current);
    }

    if (grades[grades.length - 1] !== maxValue) {
      grades.push(maxValue);
    }

    return grades;
  }

  const legendGrades = buildLegendGrades(blockedValues);
  const numberFormatter = new Intl.NumberFormat();
  const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  function formatNumber(value) {
    return numberFormatter.format(value);
  }

  function sanitizeDonutSliceEffects(chartSelector) {
    const chartRoot = document.querySelector(chartSelector);
    if (!chartRoot) {
      return;
    }

    chartRoot.classList.remove("apexcharts-tooltip-active");
    chartRoot.querySelectorAll(".apexcharts-pie-area").forEach((slice) => {
      slice.removeAttribute("filter");
      slice.removeAttribute("selected");
      slice.style.filter = "none";
    });
  }

  function queueDonutSliceSanitize(chartSelector) {
    window.setTimeout(() => {
      window.requestAnimationFrame(() =>
        sanitizeDonutSliceEffects(chartSelector),
      );
    }, 0);
  }

  function attachDonutSanitizer(chartSelector) {
    const chartRoot = document.querySelector(chartSelector);
    if (!chartRoot || chartRoot.dataset.donutSanitizerAttached === "1") {
      return;
    }

    const runSanitizer = () => queueDonutSliceSanitize(chartSelector);
    chartRoot.addEventListener("mousemove", runSanitizer, { passive: true });
    chartRoot.addEventListener("mouseenter", runSanitizer, { passive: true });
    chartRoot.addEventListener("mouseleave", runSanitizer, { passive: true });
    chartRoot.dataset.donutSanitizerAttached = "1";
  }

  function getChartSurfaceColor() {
    return theme === "dark" ? "#1b2732" : "#ffffff";
  }

  function getChartGridBorderColor() {
    return theme === "dark"
      ? "rgba(181, 206, 226, 0.18)"
      : "rgba(92, 114, 137, 0.16)";
  }

  function buildColorRamp(steps) {
    const lightnessStart = 40;
    const lightnessEnd = -30;

    if (steps <= 1) {
      return [adjustColor(baseMapColor, lightnessEnd)];
    }

    const ramp = [];
    for (let i = 0; i < steps; i++) {
      const percent =
        lightnessStart + ((lightnessEnd - lightnessStart) * i) / (steps - 1);
      ramp.push(adjustColor(baseMapColor, percent));
    }
    return ramp;
  }

  const colorRamp = buildColorRamp(Math.max(legendGrades.length - 1, 1));

  // Function to get color based on blocked requests value
  function getColor(d) {
    if (d == null || d === 0) {
      return noDataColor;
    }

    for (let i = legendGrades.length - 1; i > 0; i--) {
      if (d >= legendGrades[i]) {
        return colorRamp[Math.min(i - 1, colorRamp.length - 1)];
      }
    }

    return colorRamp[0];
  }

  // Function to style each feature
  function style(feature) {
    const blockedValue = feature.properties.value;

    return {
      fillColor: getColor(blockedValue),
      weight: 1,
      opacity: 1,
      color: "white",
      dashArray: "3",
      fillOpacity: blockedValue === 0 ? 0.2 : 0.85,
    };
  }

  // Highlight feature on hover
  function highlightFeature(e) {
    const layer = e.target;

    layer.setStyle({
      weight: 2,
      color: "#666",
      dashArray: "",
      fillOpacity: 0.7,
    });

    layer.bringToFront();

    info.update(layer.feature.properties);
  }

  // Reset highlight
  function resetHighlight(e) {
    geojson.resetStyle(e.target);
    info.update();
  }

  // Zoom to feature on click
  function zoomToFeature(e) {
    map.fitBounds(e.target.getBounds());
  }

  // Define what happens on each feature
  function onEachFeature(feature, layer) {
    layer.on({
      mouseover: highlightFeature,
      mouseout: resetHighlight,
      click: zoomToFeature,
    });
  }

  let geojson;

  // Cache for geo data
  const geoDataCache = {
    topojson: null,
    geojson: null,
  };

  // IndexedDB helper functions
  const dbName = "BunkerWebGeoData";
  const dbVersion = 1;
  const storeName = "geoData";

  function openDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(dbName, dbVersion);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(storeName)) {
          db.createObjectStore(storeName, { keyPath: "key" });
        }
      };
    });
  }

  async function getFromIndexedDB(key) {
    try {
      const db = await openDB();
      const transaction = db.transaction([storeName], "readonly");
      const store = transaction.objectStore(storeName);
      const request = store.get(key);

      return new Promise((resolve, reject) => {
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result?.data);
      });
    } catch (e) {
      console.warn("IndexedDB get failed:", e);
      return null;
    }
  }

  async function setToIndexedDB(key, data) {
    try {
      const db = await openDB();
      const transaction = db.transaction([storeName], "readwrite");
      const store = transaction.objectStore(storeName);
      const request = store.put({ key, data });

      return new Promise((resolve, reject) => {
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(true);
      });
    } catch (e) {
      console.warn("IndexedDB set failed:", e);
      return false;
    }
  }

  async function getCachedData(key) {
    // Try localStorage first (faster)
    try {
      const cached = localStorage.getItem(key);
      if (cached) {
        return JSON.parse(cached);
      }
    } catch (e) {
      console.warn("localStorage get failed, trying IndexedDB:", e);
      localStorage.removeItem(key);
    }

    // Fallback to IndexedDB
    return await getFromIndexedDB(key);
  }

  async function setCachedData(key, data) {
    const dataString = JSON.stringify(data);
    const dataSize = new Blob([dataString]).size;

    // Try localStorage first for smaller data (< 1MB)
    if (dataSize < 1024 * 1024) {
      try {
        localStorage.setItem(key, dataString);
        return true;
      } catch (e) {
        console.warn("localStorage quota exceeded, using IndexedDB:", e);
      }
    }

    // Use IndexedDB for larger data or when localStorage fails
    return await setToIndexedDB(key, data);
  }

  // Generic helper function to load and cache geo data
  async function loadAndCacheGeoData(
    cacheKey,
    memoryCache,
    url,
    processFn,
    fallbackFn = null,
  ) {
    // Check if data is already in memory cache
    if (memoryCache) {
      processFn(memoryCache);
      return;
    }

    // Try to load from persistent cache first
    const cachedData = await getCachedData(cacheKey);
    if (cachedData) {
      try {
        // Update memory cache
        if (cacheKey.includes("topojson")) {
          geoDataCache.topojson = cachedData;
        } else {
          geoDataCache.geojson = cachedData;
        }
        processFn(cachedData);
        return;
      } catch (e) {
        console.warn(`Failed to parse cached ${cacheKey} data`);
      }
    }

    // Load data from server
    $.getJSON(url, async (data) => {
      // Update memory cache
      if (cacheKey.includes("topojson")) {
        geoDataCache.topojson = data;
      } else {
        geoDataCache.geojson = data;
      }

      // Cache the data
      const cached = await setCachedData(cacheKey, data);
      if (!cached) {
        console.warn(`Failed to cache ${cacheKey} data`);
      }
      processFn(data);
    }).fail(function () {
      if (fallbackFn) {
        fallbackFn();
      }
    });
  }

  // Function to load and cache geo data
  async function loadGeoData() {
    await loadAndCacheGeoData(
      "bunkerweb_topojson_data",
      geoDataCache.topojson,
      `${baseUrl}/json/countries.topojson`,
      processTopoJSONData,
      loadGeoJSONFallback,
    );
  }

  // Function to process TopoJSON data
  function processTopoJSONData(topojsonData) {
    // Convert TopoJSON to GeoJSON
    const geojsonData = topojson.feature(
      topojsonData,
      topojsonData.objects.countries,
    );

    // Assign value to each country from requestsMapData
    geojsonData.features.forEach((feature) => {
      const isoCode = feature.properties.ISO_A2;
      const requestStats = requestsMapData[isoCode] || {};
      feature.properties.value = requestStats["blocked"] || 0; // Assign 0 if not found
      feature.properties.blocked = requestStats["blocked"] || 0; // Assign 0 if not found
    });

    // Replace the previous layer so old geometry/event listeners can be GC'ed.
    if (geojson) {
      map.removeLayer(geojson);
      geojson = null;
    }

    // Add GeoJSON layer to the map once the file is loaded
    geojson = L.geoJson(geojsonData, {
      style: style,
      onEachFeature: onEachFeature,
    }).addTo(map);
  }

  // Function to load GeoJSON as fallback
  async function loadGeoJSONFallback() {
    console.warn("Failed to load TopoJSON, falling back to GeoJSON");
    await loadAndCacheGeoData(
      "bunkerweb_geojson_data",
      geoDataCache.geojson,
      `${baseUrl}/json/countries.geojson`,
      processGeoJSONData,
    );
  }

  // Function to process GeoJSON data
  function processGeoJSONData(geojsonData) {
    geojsonData.features.forEach((feature) => {
      const isoCode = feature.properties.ISO_A2;
      const requestStats = requestsMapData[isoCode] || {};
      feature.properties.value = requestStats["blocked"] || 0;
      feature.properties.blocked = requestStats["blocked"] || 0;
    });

    if (geojson) {
      map.removeLayer(geojson);
      geojson = null;
    }

    geojson = L.geoJson(geojsonData, {
      style: style,
      onEachFeature: onEachFeature,
    }).addTo(map);
  }

  // Initialize geo data loading
  loadGeoData();

  // Add a legend to the map
  const legend = L.control({ position: "bottomright" });

  legend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend map-legend shadow");
    const gradientStops = colorRamp.join(", ");
    const grades = legendGrades;
    const bucketLabels = [];

    if (grades.length > 1) {
      for (let i = 0; i < grades.length - 1; i++) {
        const from = grades[i];
        const to = grades[i + 1];
        const labelFrom = from === 0 ? 1 : from;
        bucketLabels.push(
          `${formatNumber(labelFrom)}${to ? "–" + formatNumber(to) : "+"}`,
        );
      }
    }

    div.innerHTML = `
      <div class="map-legend__title">${t("dashboard.map.legend")}</div>
      <div class="map-legend__swatches">
        <div class="map-legend__swatch">
          <span class="map-legend__chip" style="background:${noDataColor}"></span>
          <span>${t("dashboard.map.no_data")}</span>
        </div>
      </div>
      <div class="map-legend__gradient" style="background: linear-gradient(90deg, ${gradientStops});"></div>
      <div class="map-legend__ticks">
        <span>${formatNumber(grades[0] === 0 ? 1 : grades[0])}</span>
        <span>${formatNumber(grades[grades.length - 1])}</span>
      </div>
      <div class="map-legend__ranges">${bucketLabels.join(" · ")}</div>
    `;

    return div;
  };

  legend.addTo(map);

  // Blocking timeline raw data.
  const blockingData = JSON.parse($("#requests-blocking-data").text());

  // Requests stats chart

  const requestsDataRaw = JSON.parse($("#requests-data").text());
  const requestStatusEntries = Object.entries(requestsDataRaw)
    .map(([status, count]) => [String(status), parseInt(count, 10) || 0])
    .filter(([, count]) => count > 0);

  const requestsData = Object.fromEntries(requestStatusEntries);
  const requestStatusCodes = requestStatusEntries.map(([status]) => status);
  const requestStatusSeries = requestStatusEntries.map(([, count]) => count);

  function getStatusColor(statusCodeRaw) {
    const statusCode = parseInt(statusCodeRaw, 10);
    if (!Number.isFinite(statusCode)) {
      return "#8592a3"; // neutral
    }

    // Explicit mappings requested
    if (statusCode === 200) return "#71dd37"; // green
    if (statusCode === 403) return "#ff3e1d"; // red
    if (statusCode === 429) return "#ffab00"; // yellow

    // Fallback by status class
    if (statusCode >= 500) return "#d7263d"; // dark red
    if (statusCode >= 400) return "#ff6b6b"; // light red
    if (statusCode >= 300) return "#03c3ec"; // blue
    if (statusCode >= 200) return "#71dd37"; // green
    if (statusCode >= 100) return "#8a8d93"; // gray
    return "#8592a3";
  }

  function getStatusLabel(statusCodeRaw) {
    const statusCode = parseInt(statusCodeRaw, 10);
    if (!Number.isFinite(statusCode)) {
      return String(statusCodeRaw);
    }
    if (statusCode === 200) return "200 OK";
    if (statusCode === 301) return "301 Moved";
    if (statusCode === 302) return "302 Redirect";
    if (statusCode === 304) return "304 Not Modified";
    if (statusCode === 401) return "401 Unauthorized";
    if (statusCode === 403) return "403 Blocked";
    if (statusCode === 404) return "404 Not Found";
    if (statusCode === 429) return "429 Rate Limited";
    if (statusCode >= 500) return `${statusCode} Server Error`;
    if (statusCode >= 400) return `${statusCode} Client Error`;
    if (statusCode >= 300) return `${statusCode} Redirect`;
    if (statusCode >= 200) return `${statusCode} Success`;
    return `HTTP ${statusCode}`;
  }

  const requestStatusLabels = requestStatusCodes.map((statusCode) =>
    getStatusLabel(statusCode),
  );

  const requestStatusColors = requestStatusCodes.map((statusCode) =>
    getStatusColor(statusCode),
  );

  // Ensure each value is properly converted to a number
  const totalRequests = requestStatusSeries.reduce(
    (acc, curr) => acc + parseInt(curr, 10), // Parse as integer
    0, // Initial value for the accumulator
  );

  const blockedRequests = Object.keys(requestsData).reduce((acc, key) => {
    if (["403", "429", "444"].includes(key)) {
      acc += parseInt(requestsData[key], 10); // Parse blocked requests as integer
    }
    return acc;
  }, 0); // Initial value for blocked requests accumulator

  const blockedRequestsPercent =
    totalRequests > 0
      ? ((blockedRequests / totalRequests) * 100).toFixed(2)
      : "0.00";

  var requestsChart;

  function renderStatsChart() {
    const chartSurfaceColor = getChartSurfaceColor();

    const requestsOptions = {
      chart: {
        type: "donut",
        animations: {
          enabled: true,
          easing: "easeinout",
          speed: 520,
        },
        events: {
          mounted: function () {
            queueDonutSliceSanitize("#requests-stats");
          },
          updated: function () {
            queueDonutSliceSanitize("#requests-stats");
          },
          dataPointMouseEnter: function () {
            queueDonutSliceSanitize("#requests-stats");
          },
          dataPointMouseLeave: function () {
            queueDonutSliceSanitize("#requests-stats");
          },
          dataPointSelection: function (event) {
            if (event) {
              event.preventDefault();
              event.stopPropagation();
            }
            queueDonutSliceSanitize("#requests-stats");
          },
        },
      },
      labels: requestStatusLabels,
      series: requestStatusSeries,
      colors: requestStatusColors,
      responsive: [
        {
          breakpoint: 480,
          options: {
            chart: {
              width: 200,
            },
            legend: {
              position: "bottom",
            },
          },
        },
      ],
      legend: {
        show: false,
      },
      dataLabels: {
        enabled: false,
        formatter: function (val, opt) {
          return ((parseInt(val) / totalRequests) * 100).toFixed(2) + "%";
        },
      },
      grid: {
        padding: {
          top: 0,
          bottom: 0,
          right: 15,
        },
      },
      states: {
        hover: {
          filter: { type: "none" },
        },
        active: {
          filter: { type: "none" },
        },
      },
      plotOptions: {
        pie: {
          expandOnClick: false,
          donut: {
            size: "72%",
            background: chartSurfaceColor,
            labels: {
              show: true,
              value: {
                fontSize: "20px",
                fontFamily: "Public Sans",
                fontWeight: 700,
                color: headingColor,
                offsetY: -17,
                formatter: function (val) {
                  return (
                    ((parseInt(val) / totalRequests) * 100).toFixed(2) + "%"
                  );
                },
              },
              name: {
                offsetY: 17,
                fontFamily: "Public Sans",
                color: headingColor,
                fontWeight: 600,
                formatter: function (_label, opt) {
                  if (!opt || typeof opt.seriesIndex !== "number") {
                    return "";
                  }
                  const code = requestStatusCodes[opt.seriesIndex] || "";
                  return code ? `HTTP ${code}` : "";
                },
              },
              total: {
                show: true,
                fontSize: "13px",
                color: legendColor,
                label: t("dashboard.chart.request_status.blocked"),
                formatter: function (w) {
                  return blockedRequestsPercent + "%";
                },
              },
            },
          },
        },
      },
      stroke: {
        show: true,
        width: 4,
        colors: [chartSurfaceColor],
      },
      tooltip: {
        theme: theme,
        fillSeriesColor: false,
        custom: function ({ series, seriesIndex }) {
          const code = requestStatusCodes[seriesIndex] || "";
          const label = requestStatusLabels[seriesIndex] || code || "Status";
          const color = requestStatusColors[seriesIndex] || "#8592a3";
          const value = parseInt(series[seriesIndex], 10) || 0;
          const percent =
            totalRequests > 0
              ? ((value / totalRequests) * 100).toFixed(2)
              : "0.00";
          return `
            <div class="home-chart-tooltip">
              <div class="home-chart-tooltip__row">
                <span class="home-chart-tooltip__dot" style="background:${color}"></span>
                <strong>${label}</strong>
              </div>
              <div class="home-chart-tooltip__metrics">
                <span>${formatNumber(value)} requests</span>
                <span>${percent}%</span>
              </div>
            </div>
          `;
        },
      },
    };

    requestsChart = new ApexCharts(
      document.querySelector("#requests-stats"),
      requestsOptions,
    );
    requestsChart.render();
    attachDonutSanitizer("#requests-stats");
    queueDonutSliceSanitize("#requests-stats");
  }

  renderStatsChart();

  // Requests IPs chart

  const $ipsData = $("#requests-ips-data");

  var ipsChart;

  function renderIpsChart() {
    const chartSurfaceColor = getChartSurfaceColor();
    const requestsIpsDataRaw = JSON.parse($("#requests-ips-data").text());
    const getBlockedCount = (entry) => {
      if (entry && typeof entry === "object") {
        return parseInt(entry.blocked || 0, 10) || 0;
      }
      return parseInt(entry || 0, 10) || 0;
    };
    const requestsIpsData = { ...requestsIpsDataRaw };

    // Backend now provides only top blocked IPs; keep sorting as a safety net.
    const topIpsEntries = Object.entries(requestsIpsData)
      .sort((a, b) => getBlockedCount(b[1]) - getBlockedCount(a[1]))
      .slice(0, 10);

    const topIpsData = topIpsEntries.reduce((obj, [key, value]) => {
      obj[key] = getBlockedCount(value); // only blocked requests are charted
      return obj;
    }, {});
    const topIpsLabels = Object.keys(topIpsData);
    const topIpsSeries = Object.values(topIpsData).map((value) =>
      parseInt(value, 10),
    );
    const topIpsColors = [
      "#0ea5e9",
      "#22c55e",
      "#f59e0b",
      "#ef4444",
      "#8b5cf6",
      "#14b8a6",
      "#f97316",
      "#6366f1",
      "#84cc16",
      "#06b6d4",
    ].slice(0, Math.max(topIpsLabels.length, 1));

    // Total blocked requests represented in the donut (Top 10 only)
    const topBlockedTotal = topIpsEntries.reduce(
      (sum, [, value]) => sum + getBlockedCount(value),
      0,
    );

    const ipsOptions = {
      chart: {
        type: "donut",
        animations: {
          enabled: true,
          easing: "easeinout",
          speed: 520,
        },
        events: {
          mounted: function () {
            queueDonutSliceSanitize("#requests-ips");
          },
          updated: function () {
            queueDonutSliceSanitize("#requests-ips");
          },
          dataPointMouseEnter: function () {
            queueDonutSliceSanitize("#requests-ips");
          },
          dataPointMouseLeave: function () {
            queueDonutSliceSanitize("#requests-ips");
          },
          dataPointSelection: function (event) {
            if (event) {
              event.preventDefault();
              event.stopPropagation();
            }
            queueDonutSliceSanitize("#requests-ips");
          },
        },
      },
      labels: topIpsLabels,
      series: topIpsSeries,
      colors: topIpsColors,
      responsive: [
        {
          breakpoint: 480,
          options: {
            chart: {
              width: 400,
            },
            legend: {
              position: "bottom",
            },
          },
        },
      ],
      legend: {
        show: false,
      },
      dataLabels: {
        enabled: false,
      },
      grid: {
        padding: {
          top: 0,
          bottom: 0,
          right: 15,
        },
      },
      states: {
        hover: {
          filter: { type: "none" },
        },
        active: {
          filter: { type: "none" },
        },
      },
      plotOptions: {
        pie: {
          expandOnClick: false,
          donut: {
            size: "72%",
            background: chartSurfaceColor,
            labels: {
              show: true,
              value: {
                fontSize: "20px",
                fontFamily: "Public Sans",
                fontWeight: 700,
                color: headingColor,
                offsetY: -17,
                formatter: function (val) {
                  const v = parseFloat(val) || 0;
                  if (!topBlockedTotal) return "0%";
                  return ((v / topBlockedTotal) * 100).toFixed(1) + "%";
                },
              },
              name: {
                offsetY: 17,
                fontFamily: "Public Sans",
                color: headingColor,
                fontWeight: 600,
              },
              total: {
                show: true,
                fontSize: "13px",
                color: legendColor,
                label: t("dashboard.chart.top_blocked_ips.most_blocked"),
                formatter: function () {
                  const topIP = Object.keys(topIpsData)[0];
                  return topIP || "N/A";
                },
              },
            },
          },
        },
      },
      stroke: {
        show: true,
        width: 4,
        colors: [chartSurfaceColor],
      },
      tooltip: {
        theme: theme,
        fillSeriesColor: false,
        custom: function ({ series, seriesIndex }) {
          const ipLabel = topIpsLabels[seriesIndex] || "Unknown";
          const color = topIpsColors[seriesIndex] || "#0ea5e9";
          const value = parseInt(series[seriesIndex], 10) || 0;
          const pct = topBlockedTotal
            ? ((value / topBlockedTotal) * 100).toFixed(1)
            : "0.0";
          return `
            <div class="home-chart-tooltip">
              <div class="home-chart-tooltip__row">
                <span class="home-chart-tooltip__dot" style="background:${color}"></span>
                <strong>${ipLabel}</strong>
              </div>
              <div class="home-chart-tooltip__metrics">
                <span>${formatNumber(value)} blocked</span>
                <span>${pct}% of Top 10</span>
              </div>
            </div>
          `;
        },
      },
    };

    ipsChart = new ApexCharts(
      document.querySelector("#requests-ips"),
      ipsOptions,
    );
    ipsChart.render();
    attachDonutSanitizer("#requests-ips");
    queueDonutSliceSanitize("#requests-ips");
  }

  if ($ipsData.length) {
    renderIpsChart();
  }

  // Requests Blocking status

  const blockingSeriesData = Object.entries(blockingData)
    .map(([timestamp, value]) => ({
      x: new Date(timestamp).getTime(),
      y: parseInt(value, 10) || 0,
    }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
    .sort((a, b) => a.x - b.x);

  const blockingTickAmount =
    blockingSeriesData.length > 96
      ? 12
      : Math.min(12, Math.max(4, Math.floor(blockingSeriesData.length / 8)));
  const blockingSeries = [
    {
      name: t("dashboard.chart.blocking_status.blocked_requests"),
      data: blockingSeriesData,
    },
  ];
  const blockingLineColor = getStatusColor(403);
  const peakBlockingPoint =
    blockingSeriesData.length > 0
      ? blockingSeriesData.reduce((maxPoint, currentPoint) =>
          currentPoint.y > maxPoint.y ? currentPoint : maxPoint,
        )
      : null;

  var blockingChart;

  function renderBlockingStatus() {
    const markerStrokeColor = theme === "dark" ? "#162430" : "#ffffff";
    const chartGridBorderColor = getChartGridBorderColor();

    const blockingOptions = {
      chart: {
        type: "line",
        width: "100%",
        height: 400,
        toolbar: {
          show: false,
        },
        zoom: {
          enabled: false,
        },
        animations: {
          enabled: true,
          easing: "easeinout",
          speed: 520,
        },
        fontFamily: "Public Sans, sans-serif",
      },
      title: {
        text: t("dashboard.chart.blocking_status.subtitle"),
        align: "center",
        style: {
          color: headingColor,
          fontFamily: "Public Sans, sans-serif",
        },
      },
      series: blockingSeries,
      colors: [blockingLineColor],
      stroke: {
        curve: "straight",
        width: 2.8,
        lineCap: "round",
      },
      markers: {
        size: 0,
        hover: {
          size: 6,
          sizeOffset: 2,
        },
      },
      dataLabels: {
        enabled: false,
      },
      tooltip: {
        theme: theme,
        fillSeriesColor: false,
        shared: false,
        intersect: false,
        custom: function ({ series, seriesIndex, dataPointIndex, w }) {
          const value = parseInt(series[seriesIndex][dataPointIndex], 10) || 0;
          const timestamp =
            w?.globals?.seriesX?.[seriesIndex]?.[dataPointIndex];
          const dateLabel = timestamp
            ? dateTimeFormatter.format(new Date(timestamp))
            : "";

          return `
            <div class="home-chart-tooltip">
              <div class="home-chart-tooltip__row">
                <span class="home-chart-tooltip__dot" style="background:${blockingLineColor}"></span>
                <strong>${dateLabel || t("dashboard.chart.blocking_status.time")}</strong>
              </div>
              <div class="home-chart-tooltip__metrics">
                <span>${formatNumber(value)} blocked</span>
              </div>
            </div>
          `;
        },
      },
      annotations: peakBlockingPoint
        ? {
            points: [
              {
                x: peakBlockingPoint.x,
                y: peakBlockingPoint.y,
                marker: {
                  size: 4,
                  fillColor: blockingLineColor,
                  strokeColor: markerStrokeColor,
                  strokeWidth: 2,
                },
              },
            ],
          }
        : undefined,
      xaxis: {
        type: "datetime",
        tickAmount: blockingTickAmount,
        tooltip: {
          enabled: false,
        },
        labels: {
          datetimeUTC: false,
          rotate: -30,
          style: {
            colors: headingColor,
            fontFamily: "Public Sans, sans-serif",
          },
        },
        title: {
          text: t("dashboard.chart.blocking_status.time"),
          style: {
            color: headingColor,
            fontFamily: "Public Sans, sans-serif",
          },
        },
      },
      yaxis: {
        min: 0,
        forceNiceScale: true,
        title: {
          text: t("dashboard.chart.blocking_status.count"),
          style: {
            color: headingColor,
            fontFamily: "Public Sans, sans-serif",
          },
        },
        labels: {
          formatter: function (value) {
            return formatNumber(Math.round(value || 0));
          },
          style: {
            colors: headingColor,
            fontFamily: "Public Sans, sans-serif",
          },
        },
      },
      legend: {
        show: false,
        fontFamily: "Public Sans, sans-serif",
      },
      noData: {
        text: t("status.no_data"),
      },
      grid: {
        borderColor: chartGridBorderColor,
        strokeDashArray: 4,
        padding: {
          top: 0,
          bottom: 0,
          right: 15,
        },
      },
      states: {
        hover: {
          filter: { type: "none" },
        },
        active: {
          filter: { type: "none" },
        },
      },
      responsive: [
        {
          breakpoint: 480,
          options: {
            chart: {
              width: "100%",
            },
            legend: {
              position: "bottom",
              labels: {
                color: legendColor,
              },
            },
          },
        },
      ],
    };

    blockingChart = new ApexCharts(
      document.querySelector("#requests-blocking"),
      blockingOptions,
    );
    blockingChart.render();
  }

  renderBlockingStatus();

  // Handle theme changes and language changes for charts
  function updateChartsWithTranslations() {
    // Update theme colors first
    theme = $("#theme").val();
    headingColor = config.colors.headingColor;
    legendColor = config.colors.bodyColor;
    if (theme === "dark") {
      headingColor = config.colors.white;
      legendColor = config.colors.white;
    }

    // Safely destroy and recreate charts with updated translations
    try {
      if (requestsChart) {
        requestsChart.destroy();
        requestsChart = null;
      }
      renderStatsChart();
    } catch (error) {
      console.warn("Error updating requests chart:", error);
    }

    try {
      if ($ipsData.length && ipsChart) {
        ipsChart.destroy();
        ipsChart = null;
      }
      if ($ipsData.length) {
        renderIpsChart();
      }
    } catch (error) {
      console.warn("Error updating IPs chart:", error);
    }

    try {
      if (blockingChart) {
        blockingChart.destroy();
        blockingChart = null;
      }
      renderBlockingStatus();
    } catch (error) {
      console.warn("Error updating blocking chart:", error);
    }

    // Update map labels
    if (map) {
      try {
        info.update();
        // Remove and re-add legend to update translations
        if (legend) {
          map.removeControl(legend);
          legend.addTo(map);
        }
      } catch (error) {
        console.warn("Error updating map labels:", error);
      }
    }
  }

  // Create debounced version of the update function
  const debouncedUpdateCharts = debounce(updateChartsWithTranslations, 100);

  $("#dark-mode-toggle").on("change", function () {
    setTimeout(() => {
      debouncedUpdateCharts();
    }, 30);
  });

  // Listen for language changes and update charts
  function setupLanguageChangeListener() {
    if (typeof i18next !== "undefined" && i18next.isInitialized) {
      i18next.off("languageChanged", debouncedUpdateCharts); // Remove existing listener to prevent duplicates
      i18next.on("languageChanged", () => {
        debouncedUpdateCharts();
      });
    }
  }

  // Setup language change listener immediately if i18next is ready
  setupLanguageChangeListener();

  // Wait for window.i18nextReady = true before continuing
  if (typeof window.i18nextReady === "undefined" || !window.i18nextReady) {
    const waitForI18next = (resolve) => {
      if (window.i18nextReady) {
        resolve();
      } else {
        setTimeout(() => waitForI18next(resolve), 50);
      }
    };
    new Promise((resolve) => {
      waitForI18next(resolve);
    }).then(() => {
      setupLanguageChangeListener();
      debouncedUpdateCharts();
    });
  }
});
