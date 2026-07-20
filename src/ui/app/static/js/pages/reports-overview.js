window.BWReportsDashboard = window.BWReportsDashboard || {};

(function () {
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key;
  let currentRange = {
    startEpoch: Math.floor(Date.now() / 1000) - 86400,
    endEpoch: Math.floor(Date.now() / 1000),
  };
  const listeners = [];

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

  function onRangeChange(cb) {
    listeners.push(cb);
  }

  function refresh(range) {
    currentRange = range || currentRange;
    fetchDashboard(currentRange).done((data) =>
      listeners.forEach((cb) => cb(data, currentRange)),
    );
  }

  window.BWReportsDashboard.onRangeChange = onRangeChange;
  window.BWReportsDashboard.refresh = refresh;
  window.BWReportsDashboard.currentRange = () => currentRange;

  let timeseriesChart = null;

  // ponytail: no relative-time helper/lib exists in static/js (checked reports.js, bans.js,
  // home.js, static/libs -- no dayjs/luxon/moment vendored); this minimal version covers the
  // card's needs. Upgrade to a shared util if a second page needs the same formatting.
  function relativeTime(epochSeconds) {
    if (!epochSeconds) return "—";
    const diffSec = Math.max(0, Math.floor(Date.now() / 1000) - epochSeconds);
    if (diffSec < 60) return t("flash.time.just_now", "just now");
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour}h ago`;
    const diffDay = Math.floor(diffHour / 24);
    if (diffDay < 7) return `${diffDay}d ago`;
    return new Date(epochSeconds * 1000).toLocaleDateString();
  }

  function renderOverview(data) {
    if (!data || data.status !== "success") return;
    const ts = data.timeseries || {};
    const blocked = ts.total || 0;
    // trend_pct is the % change of blocked count vs the previous equal-length window
    // (get_metrics_timeseries), rounded to 1 decimal; null when the previous window had
    // no data to compare against. More blocked requests = more attack pressure, so an
    // increase is colored as a bad-news signal (danger) and a decrease as good news
    // (success) -- the reverse of a typical "up is green" metric.
    const trendPct = ts.trend_pct;
    const $rate = $("#reports-tile-rate .bw-kpi-value");
    $rate
      .text(
        typeof trendPct === "number"
          ? `${trendPct > 0 ? "+" : ""}${trendPct}%`
          : "—",
      )
      .toggleClass("text-danger", typeof trendPct === "number" && trendPct > 0)
      .toggleClass(
        "text-success",
        typeof trendPct === "number" && trendPct < 0,
      );

    $("#reports-tile-blocked .bw-kpi-value").text(blocked);
    $("#reports-tile-unique .bw-kpi-value").text(
      new Set((data.offenders || []).map((o) => o.ip)).size,
    );

    const counts = ts.counts || [];
    const buckets = ts.buckets || [];
    let peakIdx = 0;
    counts.forEach((c, i) => {
      if (c > (counts[peakIdx] || 0)) peakIdx = i;
    });
    // blocked === 0 means every bucket is zero; peakIdx would default to bucket 0 (a real,
    // truthy epoch) and render a bogus "HH:00" instead of the empty-state placeholder.
    const peakLabel =
      blocked && buckets[peakIdx]
        ? new Date(buckets[peakIdx] * 1000).getHours() + ":00"
        : "—";
    $("#reports-tile-peak .bw-kpi-value").text(peakLabel);

    if (window.ApexCharts) {
      const host = document.getElementById("reports-timeseries-chart");
      if (host) {
        const series = [
          {
            name: t("reports.chart.timeseries.series", "Blocked"),
            data: counts,
          },
        ];
        const categories = buckets.map((b) =>
          new Date(b * 1000).toLocaleTimeString([], { hour: "2-digit" }),
        );
        if (timeseriesChart) {
          timeseriesChart.updateOptions({ series, xaxis: { categories } });
        } else {
          timeseriesChart = new ApexCharts(host, {
            chart: { type: "bar", height: 280 },
            series,
            xaxis: { categories },
          });
          timeseriesChart.render();
        }
      }
    }

    // Build rows as DOM nodes (jQuery .text()) rather than HTML-string interpolation --
    // ip/top_reason/asn_org are request-derived data (ASN org names come from a MaxMind/DB-IP
    // lookup on attacker-controlled IPs) round-tripped through the DB, so they're untrusted at
    // this sink even though they're typically well-formed. A raw-HTML setter fed a template
    // literal built from these fields would be a stored-XSS hole; .text()/DOM-append escapes
    // at the sink instead.
    function emptyStateNode() {
      return $("<p>")
        .addClass("text-muted mb-0")
        .attr("data-i18n", "status.no_data")
        .text(t("status.no_data", "No data"));
    }

    // Copy before sorting -- offenders is volume-sorted by the API and other consumers
    // (e.g. the "Top offender ASNs" aggregation below) rely on that original order.
    const recent = [...(data.offenders || [])]
      .sort((a, b) => (b.last_seen || 0) - (a.last_seen || 0))
      .slice(0, 5);
    const $incidents = $("#reports-recent-incidents").empty();
    if (recent.length) {
      const $tbody = $("<tbody>");
      recent.forEach((o) => {
        $tbody.append(
          $("<tr>").append(
            $("<td>").addClass("font-monospace").text(o.ip),
            $("<td>").text(o.top_reason),
            $("<td>").text(o.blocks),
            $("<td>")
              .addClass("text-muted small")
              .text(relativeTime(o.last_seen)),
          ),
        );
      });
      $incidents.append(
        $("<table>").addClass("table table-sm mb-0").append($tbody),
      );
    } else {
      $incidents.append(emptyStateNode());
    }

    const byOrg = {};
    (data.offenders || []).forEach((o) => {
      if (!o.asn_org) return;
      byOrg[o.asn_org] = (byOrg[o.asn_org] || 0) + o.blocks;
    });
    const topOrgs = Object.entries(byOrg)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
    const $asns = $("#reports-top-asns").empty();
    if (topOrgs.length) {
      topOrgs.forEach(([org, count]) => {
        $asns.append(
          $("<div>")
            .addClass("d-flex justify-content-between mb-1")
            .append(
              $("<span>").text(org),
              $("<span>").addClass("font-monospace").text(count),
            ),
        );
      });
    } else {
      $asns.append(emptyStateNode());
    }
  }

  onRangeChange((data) => renderOverview(data));

  $(document).ready(function () {
    window.BWRangePicker.init("reports-range");
    document.getElementById("reports-range").addEventListener("change", (e) => {
      refresh({ startEpoch: e.detail.startEpoch, endEpoch: e.detail.endEpoch });
    });
    refresh(currentRange);
  });
})();
