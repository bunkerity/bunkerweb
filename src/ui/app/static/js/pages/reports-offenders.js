(function () {
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key;

  // Matches reports.js's isReadOnly guard (read from base.html's shared #is-read-only
  // input) so this tab's ban action respects read-only mode exactly like the Event log
  // tab's "Ban selected" / per-row .ban-single actions it mirrors below.
  const isReadOnly = $("#is-read-only").val().trim() === "True";

  // Mirrors reports.js:1846-1874's .ban-single click handler (same form-POST-to-/bans/ban
  // mechanism) -- this tab's plain HTML table isn't a DataTables row, so there is no
  // DataTables ext.buttons object to reuse directly, only the underlying submit pattern.
  function submitBan(ip, serverName, reason) {
    const banScope = serverName && serverName !== "_" ? "service" : "global";
    const form = $("<form>", {
      method: "POST",
      action: `${window.location.pathname.replace("/reports", "/bans")}/ban`,
      class: "visually-hidden",
    });
    form.append(
      $("<input>", {
        type: "hidden",
        name: "csrf_token",
        value: $("#csrf_token").val(),
      }),
    );
    form.append(
      $("<input>", {
        type: "hidden",
        name: "bans",
        value: JSON.stringify([
          {
            ip,
            reason: reason || "ui",
            ban_scope: banScope,
            service: banScope === "service" ? serverName : "",
            exp: 86400,
          },
        ]),
      }),
    );
    form.appendTo("body").submit();
  }

  function emptyStateNode() {
    return $("<p>")
      .addClass("text-muted mb-0")
      .attr("data-i18n", "status.no_data")
      .text(t("status.no_data", "No data"));
  }

  // Country cell reuses the shared window.BWCountryFlag helper's safe primitives
  // (srcFor/isNA/normalize -- static/js/components/country-flag.js) instead of its html()
  // string builder. html() returns a pre-escaped markup *string* meant for a raw-HTML sink
  // (DataTables' render() callback owns the cell's innerHTML in bans.js/reports.js); this
  // tab builds a plain table with jQuery and follows the .text()-only discipline below, so
  // the flag <img> + code are built as DOM nodes instead: srcFor() returns a same-origin
  // local path derived from a regex-validated 2-letter-or-"ZZ" code (safe in a src attribute
  // regardless), and the visible label still goes through .text() like every other
  // untrusted field in this file.
  function countryCell(code) {
    return $("<span>")
      .addClass("d-inline-flex align-items-center gap-1")
      .append(
        $("<img>")
          .attr({
            src: window.BWCountryFlag.srcFor(code),
            height: 17,
            alt: "",
            "aria-hidden": "true",
          })
          .addClass("border border-1 p-0"),
        $("<span>").text(
          window.BWCountryFlag.isNA(code)
            ? "—"
            : window.BWCountryFlag.normalize(code),
        ),
      );
  }

  function render(data) {
    if (!data || data.status !== "success") return;
    const offenders = data.offenders || [];

    $("#reports-tile-uniqueoff .bw-kpi-value").text(offenders.length);
    $("#reports-tile-repeat .bw-kpi-value").text(
      offenders.filter((o) => o.blocks >= 10).length,
    );
    $("#reports-tile-countries .bw-kpi-value").text(
      new Set(offenders.map((o) => o.country).filter(Boolean)).size,
    );
    $("#reports-tile-asns .bw-kpi-value").text(
      new Set(offenders.map((o) => o.asn_org).filter(Boolean)).size,
    );

    // Top offenders table -- built as DOM nodes with jQuery .text() only. ip/asn_org/
    // top_reason are DB round-tripped, request-derived data (ASN org names come from a
    // MaxMind/DB-IP lookup on attacker-controlled IPs; see reports-overview.js's identical
    // comment) -- untrusted at this sink. No raw-HTML sink or template-literal markup
    // interpolation.
    const $host = $("#reports-offenders-table").empty();
    if (offenders.length) {
      const $thead = $("<thead>").append(
        $("<tr>").append(
          $("<th>")
            .attr("data-i18n", "reports.table.ip")
            .text(t("reports.table.ip", "IP")),
          $("<th>")
            .attr("data-i18n", "reports.table.country")
            .text(t("reports.table.country", "Country")),
          $("<th>")
            .attr("data-i18n", "reports.table.asn")
            .text(t("reports.table.asn", "ASN")),
          $("<th>")
            .attr("data-i18n", "reports.table.blocks")
            .text(t("reports.table.blocks", "Blocks")),
          $("<th>")
            .attr("data-i18n", "reports.table.top_rule")
            .text(t("reports.table.top_rule", "Top rule")),
          $("<th>"),
        ),
      );
      const $tbody = $("<tbody>");
      offenders.forEach((o) => {
        const banLabel = t("tooltip.button.ban_ip", "Ban this IP address");
        const $banBtn = $("<button>", {
          type: "button",
          class: "btn btn-outline-danger btn-sm offender-ban",
        }).attr({
          "data-ip": o.ip,
          "data-reason": o.top_reason,
          "aria-label": banLabel,
          title: banLabel,
        });
        $banBtn.append(
          $("<i>").addClass("bx bx-block bx-xs").attr("aria-hidden", "true"),
        );
        $tbody.append(
          $("<tr>").append(
            $("<td>").addClass("font-monospace").text(o.ip),
            $("<td>").append(countryCell(o.country)),
            $("<td>").text(
              o.asn_org ? `AS${o.asn_number} — ${o.asn_org}` : "N/A",
            ),
            $("<td>").addClass("font-monospace").text(o.blocks),
            $("<td>").text(o.top_reason),
            $("<td>").append($banBtn),
          ),
        );
      });
      $host.append(
        $("<table>").addClass("table table-sm mb-0").append($thead, $tbody),
      );
    } else {
      $host.append(emptyStateNode());
    }
  }

  // actionLock mirrors reports.js's .ban-single debounce (reports.js:1827,1838-1839,1889) --
  // submitBan() does a real form navigation (not AJAX), so a fast double-click before the
  // browser starts navigating could otherwise fire two POSTs.
  let actionLock = false;
  $(document).on("click", ".offender-ban", function () {
    if (isReadOnly) {
      alert(
        t("alert.readonly_mode", "This action is disabled in read-only mode."),
      );
      return;
    }
    if (actionLock) return;
    actionLock = true;
    const $btn = $(this);
    const reason = $btn.attr("data-reason") || "ui";
    submitBan($btn.attr("data-ip"), "_", reason);
    actionLock = false;
  });

  $(document).ready(function () {
    if (window.BWReportsDashboard) {
      window.BWReportsDashboard.onRangeChange(render);
    }
  });
})();
