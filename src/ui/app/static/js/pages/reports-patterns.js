(function () {
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key;

  // rule_id is DB round-tripped ModSecurity data (see get_metrics_top_rules in
  // db_methods/metrics.py) -- in practice always a numeric CRS id, but treated as
  // untrusted at the render sink per the Task 9 XSS discipline (reports-overview.js).
  // Object.create(null) drops the prototype chain so a lookup keyed on an
  // attacker-influenced prefix can never resolve to an inherited property
  // (constructor/toString/__proto__/...) instead of undefined.
  // Real OWASP CRS convention (942xxx=SQLi, 932xxx=RCE); extend if more families
  // are wanted later.
  const RULE_FAMILY = Object.create(null);
  RULE_FAMILY["942"] = "sqli";
  RULE_FAMILY["932"] = "rce";

  function familyFor(ruleId) {
    const prefix = String(ruleId).slice(0, 3);
    return RULE_FAMILY[prefix] || null;
  }

  // Percentage-bar labels for the families keyed by rule fires (sqli/rce). Bot activity is
  // counted from a different dataset/unit (distinct offender IPs, not rule fires -- see the
  // botCount comment below) and is intentionally excluded from this map/the bars: mixing it
  // into a rule-fire-based percentage would produce a misleading number. Reuses the KPI tile
  // labels so the family name shown here always matches the tile above it.
  const FAMILY_LABEL_KEY = {
    sqli: "reports.tile.sqli",
    rce: "reports.tile.rce",
  };

  function emptyStateNode() {
    return $("<p>")
      .addClass("text-muted mb-0")
      .attr("data-i18n", "status.no_data")
      .text(t("status.no_data", "No data"));
  }

  function render(data) {
    if (!data || data.status !== "success") return;
    const rules = data.rules || [];
    const offenders = data.offenders || [];

    // sqli/rce are tallied from the top-10 most-fired rule IDs (get_metrics_top_rules'
    // API-side limit) -- an undercount if non-942/932 rules crowd out the top 10, acceptable
    // for a v1 KPI without a dedicated endpoint.
    const familyCounts = { sqli: 0, rce: 0 };
    rules.forEach((r) => {
      const fam = familyFor(r.rule_id);
      if (fam) familyCounts[fam] += r.count;
    });
    // Distinct offender IPs whose most common block reason is antibot -- a different unit
    // than familyCounts (rule fires), so kept separate and out of the percentage bars below.
    const botCount = offenders.filter((o) =>
      String(o.top_reason).toLowerCase().includes("antibot"),
    ).length;

    $("#reports-tile-sqli .bw-kpi-value").text(familyCounts.sqli);
    $("#reports-tile-rce .bw-kpi-value").text(familyCounts.rce);
    $("#reports-tile-bot .bw-kpi-value").text(botCount);

    // Top ModSecurity rules table -- built as DOM nodes with jQuery .text() only.
    // rule_id is untrusted (see RULE_FAMILY comment above): no raw-HTML sink or
    // template-literal markup interpolation, matching reports-overview.js's
    // established discipline.
    const $rulesHost = $("#reports-top-rules").empty();
    if (rules.length) {
      const $thead = $("<thead>").append(
        $("<tr>").append(
          $("<th>")
            .attr("data-i18n", "reports.table.rule")
            .text(t("reports.table.rule", "Rule")),
          $("<th>")
            .attr("data-i18n", "reports.table.fires")
            .text(t("reports.table.fires", "Fires")),
        ),
      );
      const $tbody = $("<tbody>");
      rules.forEach((r) => {
        $tbody.append(
          $("<tr>").append(
            $("<td>").append(
              $("<span>").addClass("badge bg-danger").text(`CRS ${r.rule_id}`),
            ),
            $("<td>").addClass("font-monospace").text(r.count),
          ),
        );
      });
      $rulesHost.append(
        $("<table>").addClass("table table-sm mb-0").append($thead, $tbody),
      );
    } else {
      $rulesHost.append(emptyStateNode());
    }

    // Attack families -- share of top-rule fires per family (sqli/rce only; see botCount
    // comment above for why bot activity isn't mixed into this rule-fire-based percentage).
    const totalRuleFires = rules.reduce((sum, r) => sum + r.count, 0) || 1;
    const present = Object.entries(familyCounts).filter(
      ([, count]) => count > 0,
    );
    const $familiesHost = $("#reports-attack-families").empty();
    if (present.length) {
      present.forEach(([fam, count]) => {
        const labelKey = FAMILY_LABEL_KEY[fam];
        $familiesHost.append(
          $("<div>")
            .addClass("d-flex justify-content-between mb-1")
            .append(
              $("<span>").attr("data-i18n", labelKey).text(t(labelKey, fam)),
              $("<span>")
                .addClass("font-monospace")
                .text(`${Math.round((count / totalRuleFires) * 100)}%`),
            ),
        );
      });
    } else {
      $familiesHost.append(emptyStateNode());
    }
  }

  $(document).ready(function () {
    if (window.BWReportsDashboard) {
      window.BWReportsDashboard.onRangeChange(render);
    }
  });
})();
