/* "Active bans per interval" panel on /bans (#3820).
 *
 * Mirrors home-dashboard.js: the range picker dispatches a `change` CustomEvent, we POST the
 * window to /bans/timeseries and repaint one ApexCharts area chart. BWRangePicker.init() does
 * not fire for the preset that is already active on load, so the first fetch computes the same
 * 24h window the template renders as active itself.
 */
(function () {
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key;

  let currentRange = {
    startEpoch: Math.floor(Date.now() / 1000) - 86400,
    endEpoch: Math.floor(Date.now() / 1000),
  };
  let chart = null;

  function fetchSeries(range) {
    return $.ajax({
      url: `${window.location.pathname}/timeseries`,
      type: "POST",
      data: {
        csrf_token: $("#csrf_token").val(),
        start: range.startEpoch,
        end: range.endEpoch,
        bucket: range.endEpoch - range.startEpoch > 7 * 86400 ? "day" : "hour",
      },
    });
  }

  function renderChart(timeseries) {
    if (!window.ApexCharts) return;
    const host = document.getElementById("bans-timeseries-chart");
    if (!host) return;

    const series = [
      {
        name: t("bans.chart.timeseries.series", "Active bans"),
        data: timeseries.counts || [],
      },
    ];
    const categories = (timeseries.buckets || []).map((bucketEpoch) =>
      new Date(bucketEpoch * 1000).toLocaleDateString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
      }),
    );

    if (chart) {
      chart.updateOptions({ series, xaxis: { categories } });
      return;
    }
    chart = new ApexCharts(host, {
      chart: { type: "area", height: 260, toolbar: { show: false } },
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
    chart.render();
  }

  function refresh(range) {
    currentRange = range || currentRange;
    fetchSeries(currentRange).done((data) => {
      if (!data || data.status !== "success") return;
      renderChart(data.timeseries || {});
    });
  }

  $(document).ready(() => {
    const picker = document.getElementById("bans-range");
    if (picker && window.BWRangePicker) {
      window.BWRangePicker.init("bans-range");
      picker.addEventListener("change", (event) => {
        refresh({
          startEpoch: event.detail.startEpoch,
          endEpoch: event.detail.endEpoch,
        });
      });
    }
    refresh(currentRange);
  });
})();
