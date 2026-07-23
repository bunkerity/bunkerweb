window.BWBansStats = window.BWBansStats || {};

(function () {
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key;

  function fetchStats() {
    return $.ajax({
      url: `${window.location.pathname}/stats`,
      type: "POST",
      data: {
        csrf_token: $("#csrf_token").val(),
      },
    });
  }

  function emptyStateNode() {
    return $("<p>")
      .addClass("text-muted mb-0")
      .attr("data-i18n", "status.no_data")
      .text(t("status.no_data", "No data"));
  }

  // Build rows as DOM nodes (jQuery .text()) rather than HTML-string interpolation --
  // `reason` is untrusted free text (operator/rule/UA-derived), so it must go through
  // an escaping sink instead of a raw-HTML setter.
  function renderReasonBreakdown(reasons) {
    const $body = $("#bans-reason-breakdown").empty();
    if (!reasons || !reasons.length) {
      $body.append(emptyStateNode());
      return;
    }
    reasons.forEach((r) => {
      const pct = typeof r.pct === "number" ? r.pct : 0;
      $body.append(
        $("<div>")
          .addClass("d-flex justify-content-between align-items-center mb-1")
          .append(
            $("<span>").text(r.reason),
            $("<span>")
              .addClass("font-monospace small text-muted")
              .text(`${pct}%`),
          ),
        $("<div>")
          .addClass("progress mb-3")
          .css("height", "6px")
          .append(
            $("<div>").addClass("progress-bar").css("width", `${pct}%`).attr({
              role: "progressbar",
              "aria-valuenow": pct,
              "aria-valuemin": 0,
              "aria-valuemax": 100,
            }),
          ),
      );
    });
  }

  function renderStats(data) {
    if (!data) return;
    $("#bans-tile-active .bw-kpi-value").text(data.active ?? 0);
    $("#bans-tile-expiring .bw-kpi-value").text(data.expiring_1h ?? 0);
    $("#bans-tile-countries .bw-kpi-value").text(data.countries ?? 0);
    $("#bans-tile-permanent .bw-kpi-value").text(data.permanent ?? 0);
    renderReasonBreakdown(data.reason_breakdown);
  }

  function refresh() {
    return fetchStats().done((data) => renderStats(data));
  }

  window.BWBansStats.refresh = refresh;

  $(document).ready(function () {
    refresh();
  });
})();
