window.BWBansStats = window.BWBansStats || {};

(function () {
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key;

  function fetchStats(detail) {
    return $.ajax({
      url: `${window.location.pathname}/stats`,
      type: "POST",
      data: {
        csrf_token: $("#csrf_token").val(),
        // Set by bans.js once the instances report CrowdSec leases the database does not hold yet.
        ...(window.BWBansStats.runtimeLeases ? { runtime_leases: "1" } : {}),
        ...(detail ? { detail: "1" } : {}),
      },
    });
  }

  function emptyStateNode() {
    return $("<p>")
      .addClass("text-muted mb-0")
      .attr("data-i18n", "status.no_data")
      .text(t("status.no_data", "No data"));
  }

  function tableOptions(reasons) {
    return {
      items: reasons.map((r) => ({
        label: r.reason,
        pct: typeof r.pct === "number" ? r.pct : 0,
      })),
      head: {
        label: t("bans.stats.reasons.head_reason", "Reason"),
        share: t("tables.top.share", "Share"),
      },
      caption: t("bans.stats.card.by_reason", "Bans by reason"),
    };
  }

  function openDetail(activeBans) {
    fetchStats(true).done((data) => {
      if (!data || !data.reason_breakdown || !data.reason_breakdown.length)
        return;
      window.BWTopTable.openDetail({
        ...tableOptions(data.reason_breakdown),
        title: t("bans.stats.card.by_reason", "Bans by reason"),
        meta: t("bans.stats.reasons.meta", "{{count}} active bans", {
          count: activeBans,
        }),
        closeLabel: t("button.close", "Close"),
      });
    });
  }

  // Labels are untrusted free text (operator/rule/UA-derived): BWTopTable builds every cell with
  // jQuery .text(), never an HTML string.
  function renderReasonBreakdown(reasons, activeBans) {
    const $body = $("#bans-reason-breakdown").empty();
    if (!reasons || !reasons.length) {
      $body.append(emptyStateNode());
      return;
    }
    window.BWTopTable.render($body, {
      ...tableOptions(reasons),
      detailLabel: t("tables.top.detail", "Detail"),
      onDetail: () => openDetail(activeBans),
    });
  }

  function renderStats(data) {
    if (!data) return;
    $("#bans-tile-active .bw-kpi-value").text(data.active ?? 0);
    $("#bans-tile-expiring .bw-kpi-value").text(data.expiring_1h ?? 0);
    $("#bans-tile-countries .bw-kpi-value").text(data.countries ?? 0);
    $("#bans-tile-permanent .bw-kpi-value").text(data.permanent ?? 0);
    renderReasonBreakdown(data.reason_breakdown, data.active ?? 0);
  }

  function refresh() {
    return fetchStats().done((data) => renderStats(data));
  }

  window.BWBansStats.refresh = refresh;

  $(document).ready(function () {
    refresh();
  });
})();
