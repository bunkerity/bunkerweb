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
  function submitBans(targets) {
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
        value: JSON.stringify(
          targets.map(({ ip, serverName, reason }) => {
            const banScope =
              serverName && serverName !== "_" ? "service" : "global";
            return {
              ip,
              reason: reason || "ui",
              ban_scope: banScope,
              service: banScope === "service" ? serverName : "",
              exp: 86400,
            };
          }),
        ),
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

  // Table state: the API returns the offenders volume-sorted; the toolbar re-sorts and filters
  // that list client-side, nothing is asked of the server again.
  let offenders = [];
  let query = "";
  let sortMode = "top";
  const selected = new Set();

  const SORTS = {
    top: (a, b) => b.blocks - a.blocks,
    bottom: (a, b) => a.blocks - b.blocks,
    latest: (a, b) => (b.last_seen || 0) - (a.last_seen || 0),
  };

  function visibleOffenders() {
    const needle = query.trim().toLowerCase();
    return offenders
      .filter(
        (o) =>
          !needle ||
          [o.ip, o.country, o.asn_org, o.asn_number, o.top_reason]
            .join(" ")
            .toLowerCase()
            .includes(needle),
      )
      .sort(SORTS[sortMode]);
  }

  const labels = () => ({
    ip: t("reports.table.ip", "IP"),
    country: t("reports.table.country", "Country"),
    asn: t("reports.table.asn", "ASN"),
    blocks: t("reports.table.blocks", "Blocks"),
    rule: t("reports.table.top_rule", "Top rule"),
  });

  async function confirmBan(targets) {
    if (isReadOnly) {
      alert(
        t("alert.readonly_mode", "This action is disabled in read-only mode."),
      );
      return;
    }
    if (actionLock || !targets.length) return;
    actionLock = true;
    const single = targets.length === 1;
    const confirmed = await window.BWConfirm.open({
      title: t("reports.offenders.confirm_title", "Ban from the reports"),
      message: single
        ? t(
            "reports.offenders.confirm_one",
            "{{ip}} will be banned on every instance for 24 hours.",
            { ip: targets[0].ip },
          )
        : t(
            "reports.offenders.confirm_many",
            "{{count}} IP addresses will be banned on every instance for 24 hours.",
            { count: targets.length },
          ),
      confirmLabel: t("button.ban", "Ban"),
    });
    // The page navigates on submit, which releases the lock.
    if (confirmed) submitBans(targets);
    else actionLock = false;
  }

  const asTarget = (o) => ({ ip: o.ip, serverName: "_", reason: o.top_reason });

  function csvOf(list) {
    const names = labels();
    const quote = (value) => {
      const text = String(value ?? "");
      // A cell starting with = + - @ would be run as a formula by a spreadsheet.
      return `"${(/^[=+\-@\t\r]/.test(text) ? `'${text}` : text).replace(/"/g, '""')}"`;
    };
    return [
      [names.ip, names.country, names.asn, names.blocks, names.rule],
      ...list.map((o) => [
        o.ip,
        o.country,
        o.asn_org ? `AS${o.asn_number} ${o.asn_org}` : "",
        o.blocks,
        o.top_reason,
      ]),
    ]
      .map((line) => line.map(quote).join(","))
      .join("\r\n");
  }

  function toolbar() {
    const $search = $("<input>", {
      type: "search",
      class: "form-control form-control-sm",
      autocomplete: "off",
      value: query,
      placeholder: t("form.placeholder.search", "Search..."),
      "aria-label": t("form.placeholder.search", "Search..."),
    }).on("input", function () {
      query = this.value;
      renderTable();
    });
    const $sort = $("<select>", {
      class: "form-select form-select-sm w-auto",
      "aria-label": t("reports.offenders.show", "Show"),
    }).append(
      ["top", "latest", "bottom"].map((mode) =>
        $("<option>")
          .val(mode)
          .prop("selected", mode === sortMode)
          .text(
            t(
              `reports.offenders.show_${mode}`,
              {
                top: "Top offenders",
                latest: "Latest offenders",
                bottom: "Bottom offenders",
              }[mode],
            ),
          ),
      ),
    );
    $sort.on("change", function () {
      sortMode = this.value;
      renderTable();
    });
    const $export = $("<button>", {
      type: "button",
      class: "btn btn-minor btn-sm btn-light",
    })
      .append(
        $("<i>").addClass("bx bx-download").attr("aria-hidden", "true"),
        $("<span>").text(` ${t("button.export", "Export")} CSV`),
      )
      .on("click", () => {
        const link = document.createElement("a");
        link.href = URL.createObjectURL(
          new Blob(["\ufeff", csvOf(visibleOffenders())], {
            type: "text/csv;charset=utf-8",
          }),
        );
        link.download = "bw_offenders.csv";
        link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 1000);
      });
    const none = selected.size === 0;
    const $ban = $("<button>", {
      type: "button",
      class: "btn btn-minor btn-sm btn-light text-danger",
      "aria-disabled": String(none),
    })
      .append(
        $("<i>").addClass("bx bx-block").attr("aria-hidden", "true"),
        $("<span>").text(` ${t("button.ban_selected", "Ban selected")}`),
      )
      .on("click", () => {
        if (selected.size)
          confirmBan(offenders.filter((o) => selected.has(o.ip)).map(asTarget));
      });
    // aria-disabled (not disabled) keeps the button focusable so its tooltip stays reachable.
    const $banHost = $("<span>")
      .addClass("d-inline-block")
      .attr({
        "data-bs-toggle": none ? "tooltip" : null,
        "data-bs-original-title": t(
          "table_system.multiple_actions",
          "Multiple actions for selected items",
        ),
      })
      .append($ban);
    if (none) new bootstrap.Tooltip($banHost[0]);
    return $("<div>")
      .addClass("d-flex flex-wrap align-items-center gap-2 mb-3")
      .append(
        $export,
        $banHost,
        $sort,
        $("<div>").addClass("ms-auto").append($search),
      );
  }

  function renderTable() {
    const list = visibleOffenders();
    const names = labels();
    const $host = $("#reports-offenders-table");
    const search = $host.find("input[type=search]")[0];
    const hadFocus = search && document.activeElement === search;
    const selection = hadFocus
      ? [search.selectionStart, search.selectionEnd, search.selectionDirection]
      : null;
    $host.empty();
    if (!offenders.length) {
      $host.append(emptyStateNode());
      return;
    }
    $host.append(toolbar());
    if (hadFocus) {
      const replacement = $host.find("input[type=search]")[0];
      replacement.focus();
      replacement.setSelectionRange(...selection);
    }
    if (!list.length) {
      $host.append(emptyStateNode());
      return;
    }
    const $all = $("<input>", {
      type: "checkbox",
      "aria-label": t("datatable.select_row", "Select row"),
    })
      .prop(
        "checked",
        list.every((o) => selected.has(o.ip)),
      )
      .on("change", function () {
        list.forEach((o) =>
          this.checked ? selected.add(o.ip) : selected.delete(o.ip),
        );
        renderTable();
      });
    const $thead = $("<thead>").append(
      $("<tr>").append(
        $("<th>").addClass("bw-checkbox").append($all),
        $("<th>").text(names.ip),
        $("<th>").text(names.country),
        $("<th>").text(names.asn),
        $("<th>").text(names.blocks),
        $("<th>").text(names.rule),
        $("<th>").addClass("actions-col"),
      ),
    );
    const $tbody = $("<tbody>");
    list.forEach((o) => {
      const banLabel = t("tooltip.button.ban_ip", "Ban this IP address");
      const $box = $("<input>", {
        type: "checkbox",
        "aria-label": `${t("datatable.select_row", "Select row")}: ${o.ip}`,
      })
        .prop("checked", selected.has(o.ip))
        .on("change", function () {
          if (this.checked) selected.add(o.ip);
          else selected.delete(o.ip);
          renderTable();
        });
      const $banBtn = $("<button>", {
        type: "button",
        class: "icon-btn ban offender-ban",
      }).attr({
        "data-ip": o.ip,
        "data-reason": o.top_reason,
        "aria-label": banLabel,
        title: banLabel,
      });
      $banBtn.append(
        $("<i>").addClass("bx bx-block").attr("aria-hidden", "true"),
      );
      $tbody.append(
        $("<tr>").append(
          $("<td>").addClass("bw-checkbox").append($box),
          $("<td>").append($("<span>").addClass("cell-ip").text(o.ip)),
          $("<td>").append(countryCell(o.country)),
          $("<td>").text(
            o.asn_org ? `AS${o.asn_number} — ${o.asn_org}` : "N/A",
          ),
          $("<td>").addClass("font-monospace").text(o.blocks),
          $("<td>").append(
            $("<span>")
              .addClass("tag-chip plugin-chip")
              .append(
                $("<i>")
                  .addClass("bx bx-shield-quarter")
                  .attr("aria-hidden", "true"),
                $("<span>").text(o.top_reason),
              ),
          ),
          $("<td>").addClass("actions-col").append($banBtn),
        ),
      );
    });
    $host.append(
      $("<div>")
        .addClass("bw-table-scroll")
        .append(
          $("<table>").addClass("table table-sm mb-0").append($thead, $tbody),
        ),
    );
  }

  function render(data) {
    if (!data || data.status !== "success") return;
    offenders = data.offenders || [];
    selected.clear();

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

    // The table is built as DOM nodes with jQuery .text() only: ip/asn_org/top_reason are
    // DB round-tripped, request-derived data (ASN org names come from a MaxMind/DB-IP lookup on
    // attacker-controlled IPs) -- untrusted at this sink.
    renderTable();
  }

  // actionLock mirrors reports.js's .ban-single debounce (reports.js:1827,1838-1839,1889) --
  // submitBan() does a real form navigation (not AJAX), so a fast double-click before the
  // browser starts navigating could otherwise fire two POSTs.
  let actionLock = false;
  $(document).on("click", ".offender-ban", function () {
    const $btn = $(this);
    confirmBan([
      {
        ip: $btn.attr("data-ip"),
        serverName: "_",
        reason: $btn.attr("data-reason") || "ui",
      },
    ]);
  });

  $(document).ready(function () {
    if (window.BWReportsDashboard) {
      window.BWReportsDashboard.onRangeChange(render);
    }
  });
})();
