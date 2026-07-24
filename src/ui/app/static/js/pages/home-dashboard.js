(function () {
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key;

  // Default window matches the range-picker's server-rendered active="7d" preset
  // (home.html) -- BWRangePicker.init() doesn't fire a synthetic change event for
  // the preset that's already active on load, so the initial fetch below has to
  // compute the same window itself (mirrors reports-overview.js's identical
  // 24h-default pattern for the "24h" reports picker).
  let currentRange = {
    startEpoch: Math.floor(Date.now() / 1000) - 7 * 86400,
    endEpoch: Math.floor(Date.now() / 1000),
  };

  function fetchDashboard(range) {
    return $.ajax({
      url: `${window.location.pathname}/dashboard`,
      type: "POST",
      data: {
        csrf_token: $("#csrf_token").val(),
        start: range.startEpoch,
        end: range.endEpoch,
        bucket: "hour",
      },
    });
  }

  let timeseriesChart = null;

  function renderTrendTile(trendPct) {
    // trend_pct is the % change of blocked count vs. the previous equal-length window
    // (get_metrics_timeseries) -- more blocked requests is bad news, so an increase is
    // colored danger and a decrease success (see reports-overview.js's identical tile).
    // Feeds the status band's "Blocked Requests" trend chip (#home-blocked-trend).
    const $chip = $("#home-blocked-trend");
    if (!$chip.length) return;
    const hasVal = typeof trendPct === "number";
    const up = hasVal && trendPct > 0;
    const down = hasVal && trendPct < 0;
    const suffix = t("dashboard.status.vs_prev", "vs prev.");
    $chip
      .removeClass("sb-chip-green sb-chip-danger sb-chip-muted")
      .addClass(
        up ? "sb-chip-danger" : down ? "sb-chip-green" : "sb-chip-muted",
      )
      .removeAttr("data-i18n")
      .empty();
    if (up || down) {
      $chip.append(
        $("<i>", {
          class: `bx ${up ? "bx-up-arrow-alt" : "bx-down-arrow-alt"}`,
          "aria-hidden": "true",
        }),
      );
    }
    $chip.append(
      document.createTextNode(
        `${hasVal ? `${trendPct > 0 ? "+" : ""}${trendPct}% ` : ""}${suffix}`,
      ),
    );
  }

  function renderChart(timeseries) {
    if (!window.ApexCharts) return;
    const host = document.getElementById("home-timeseries-chart");
    if (!host) return;

    const counts = timeseries.counts || [];
    const buckets = timeseries.buckets || [];
    const series = [
      {
        name: t("dashboard.chart.timeseries.series", "Blocked"),
        data: counts,
      },
    ];
    const categories = buckets.map((bucketEpoch) =>
      new Date(bucketEpoch * 1000).toLocaleDateString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
      }),
    );

    if (timeseriesChart) {
      timeseriesChart.updateOptions({ series, xaxis: { categories } });
      return;
    }
    timeseriesChart = new ApexCharts(host, {
      chart: { type: "area", height: 280, toolbar: { show: false } },
      series,
      xaxis: { categories },
      dataLabels: { enabled: false },
      stroke: { curve: "smooth", width: 2 },
      fill: {
        type: "gradient",
        gradient: { opacityFrom: 0.35, opacityTo: 0.02 },
      },
      noData: { text: t("status.no_data", "No data") },
    });
    timeseriesChart.render();
  }

  function render(data) {
    if (!data || data.status !== "success") return;
    const timeseries = data.timeseries || {};
    renderTrendTile(timeseries.trend_pct);
    renderChart(timeseries);
  }

  function refresh(range) {
    currentRange = range || currentRange;
    fetchDashboard(currentRange).done(render);
  }

  $(document).ready(function () {
    window.BWRangePicker.init("home-range");
    document.getElementById("home-range").addEventListener("change", (e) => {
      refresh({ startEpoch: e.detail.startEpoch, endEpoch: e.detail.endEpoch });
    });
    refresh(currentRange);
  });
})();
