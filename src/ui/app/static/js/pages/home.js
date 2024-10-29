$(function () {
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
    this._div.innerHTML = props
      ? `
          <div class="card shadow-none p-1">
              <div class="card-header p-1 pb-0">
                  <h5 class="card-title mb-0">${props.ADMIN}</h5>
              </div>
              <div class="card-body p-1 pt-1">
                  <p class="card-text">Blocked Requests: ${props.blocked}</p>
              </div>
          </div>
      `
      : `
          <div class="alert alert-primary" role="alert">
              Hover over a country
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

  // Function to get color based on data value, using a gradient of "#0b354a"
  function getColor(d) {
    if (d == null || d === 0) {
      return "transparent"; // No data, make it transparent
    }

    // Calculate shades based on data range
    if (d > 1000) {
      return adjustColor("#0b354a", -30); // Even darker
    } else if (d > 500) {
      return adjustColor("#0b354a", -20); // Darker shade
    } else if (d > 200) {
      return adjustColor("#0b354a", -10); // Slightly dark
    } else if (d > 100) {
      return adjustColor("#0b354a", 0); // Base color
    } else if (d > 50) {
      return adjustColor("#0b354a", 10); // Slightly light
    } else if (d > 20) {
      return adjustColor("#0b354a", 20); // Lighter shade
    } else if (d > 10) {
      return adjustColor("#0b354a", 30); // Even lighter
    } else {
      return adjustColor("#0b354a", 40); // Very light shade
    }
  }

  // Function to style each feature
  function style(feature) {
    return {
      fillColor: getColor(feature.properties.value),
      weight: 1,
      opacity: 1,
      color: "white",
      dashArray: "3",
      fillOpacity:
        feature.properties.value == null || feature.properties.value === 0
          ? 0
          : 0.7,
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

  // Load GeoJSON data and add to map
  $.getJSON(`${baseUrl}/json/countries.geojson`, (geojsonData) => {
    // Assign value to each country from requestsMapData
    geojsonData.features.forEach((feature) => {
      const isoCode = feature.properties.ISO_A2;
      feature.properties.value =
        (requestsMapData[isoCode] || {})["request"] || 0; // Assign 0 if not found
      feature.properties.blocked =
        (requestsMapData[isoCode] || {})["blocked"] || 0; // Assign 0 if not found
    });

    // Add GeoJSON layer to the map once the file is loaded
    geojson = L.geoJson(geojsonData, {
      style: style,
      onEachFeature: onEachFeature,
    }).addTo(map);
  });

  // Add a legend to the map
  const legend = L.control({ position: "bottomright" });

  legend.onAdd = function () {
    const div = L.DomUtil.create("div", "legend shadow"),
      grades = [0, 10, 20, 50, 100, 200, 500, 1000],
      labels = ['<i style="background:transparent"></i> No data'];

    div.innerHTML =
      '<div class="card mb-1"><div class="card-body text-center p-1"><strong>Legend</strong><br>';

    for (let i = 0; i < grades.length; i++) {
      const from = grades[i];
      const to = grades[i + 1];

      labels.push(
        '<i style="background:' +
          getColor(from + 1) +
          '"></i> ' +
          from +
          (to ? "&ndash;" + to : "+"),
      );
    }

    div.innerHTML += labels.join("<br>") + "</div></div>";
    return div;
  };

  legend.addTo(map);

  // Requests stats chart

  const requestsData = JSON.parse($("#requests-data").text());

  // Ensure each value is properly converted to a number
  const totalRequests = Object.values(requestsData).reduce(
    (acc, curr) => acc + parseInt(curr, 10), // Parse as integer
    0, // Initial value for the accumulator
  );

  const blockedRequests = Object.keys(requestsData).reduce((acc, key) => {
    if (["403", "444"].includes(key)) {
      acc += parseInt(requestsData[key], 10); // Parse blocked requests as integer
    }
    return acc;
  }, 0); // Initial value for blocked requests accumulator

  const blockedRequestsPercent = (
    (blockedRequests / totalRequests) *
    100
  ).toFixed(2);

  var requestsChart;

  function renderStatsChart() {
    const requestsOptions = {
      chart: {
        type: "donut",
      },
      labels: Object.keys(requestsData),
      series: Object.values(requestsData).map((value) => parseInt(value, 10)),
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
          donut: {
            size: "75%",
            labels: {
              show: true,
              value: {
                fontSize: "18px",
                fontFamily: "Public Sans",
                fontWeight: 500,
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
              },
              total: {
                show: true,
                fontSize: "13px",
                color: legendColor,
                label: "Blocked",
                formatter: function (w) {
                  return blockedRequestsPercent + "%";
                },
              },
            },
          },
        },
      },
    };

    requestsChart = new ApexCharts(
      document.querySelector("#requests-stats"),
      requestsOptions,
    );
    requestsChart.render();
  }

  renderStatsChart();

  // Requests IPs chart

  const $ipsData = $("#requests-ips-data");

  var ipsChart;

  function renderIpsChart() {
    const requestsIpsData = JSON.parse($("#requests-ips-data").text());

    const topIpsData = Object.entries(requestsIpsData)
      .sort((a, b) => b[1]["blocked"] - a[1]["blocked"])
      .slice(0, 10)
      .reduce((obj, [key, value]) => {
        obj[key] = value["blocked"];
        return obj;
      }, {});

    const ipsOptions = {
      chart: {
        type: "donut",
      },
      labels: Object.keys(topIpsData),
      series: Object.values(topIpsData).map((value) => parseInt(value, 10)),
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
          donut: {
            size: "75%",
            labels: {
              show: true,
              value: {
                fontSize: "18px",
                fontFamily: "Public Sans",
                fontWeight: 500,
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
              },
            },
          },
        },
      },
    };

    ipsChart = new ApexCharts(
      document.querySelector("#requests-ips"),
      ipsOptions,
    );
    ipsChart.render();
  }

  if ($ipsData.length) {
    renderIpsChart();
  }

  // Requests Blocking status

  const blockingData = JSON.parse($("#requests-blocking-data").text());

  const dataValues = Object.values(blockingData).map((value) =>
    parseInt(value, 10),
  );
  const categories = Object.keys(blockingData).map((key) =>
    new Date(key).toLocaleTimeString(),
  );

  const minValue = Math.min(...dataValues);
  const maxValue = Math.max(...dataValues);

  // Function to map a ratio to a color from green to red
  function getColorFromRatio(ratio) {
    const hue = (1 - ratio) * 120; // 120 (green) to 0 (red)
    return `hsl(${hue}, 100%, 50%)`;
  }

  // Generate colors for each data point
  const colorValues = dataValues.map((value) => {
    const ratio = (value - minValue) / (maxValue - minValue);
    return getColorFromRatio(ratio);
  });

  var blockingChart;

  function renderBlockingStatus() {
    const blockingOptions = {
      chart: {
        type: "bar",
        width: "100%",
        height: 400,
        toolbar: {
          show: false,
        },
      },
      title: {
        text: "Blocked Requests per Hour",
        align: "center",
        style: {
          color: headingColor,
        },
      },
      series: [
        {
          name: "Blocked Requests",
          data: dataValues,
        },
      ],
      colors: colorValues,
      plotOptions: {
        bar: {
          distributed: true,
        },
      },
      xaxis: {
        categories: categories,
        labels: {
          rotate: -45,
          hideOverlappingLabels: true,
          style: {
            colors: headingColor,
          },
        },
        title: {
          text: "Time",
          style: {
            color: headingColor,
          },
        },
      },
      yaxis: {
        title: {
          text: "Number of Blocked Requests",
          style: {
            color: headingColor,
          },
        },
      },
      legend: {
        show: false,
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

  $("#dark-mode-toggle").on("change", function () {
    setTimeout(() => {
      theme = $("#theme").val();
      headingColor = config.colors.headingColor;
      legendColor = config.colors.bodyColor;
      if (theme === "dark") {
        headingColor = config.colors.white;
        legendColor = config.colors.white;
      }

      requestsChart.destroy();
      renderStatsChart();
      if ($ipsData.length) {
        ipsChart.destroy();
        renderIpsChart();
      }
      blockingChart.destroy();
      renderBlockingStatus();
    }, 30);
  });
});
