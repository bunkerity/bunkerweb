(async function waitForDependencies() {
  // Wait for jQuery
  while (typeof jQuery === "undefined") {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  // Wait for $ to be available (in case of jQuery.noConflict())
  while (typeof $ === "undefined") {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  // Wait for DataTable to be available
  while (typeof $.fn.DataTable === "undefined") {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  const escapeHtml = (str) => {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };

  $(document).ready(function () {
    const t =
      typeof i18next !== "undefined"
        ? i18next.t
        : (key, fallback) => fallback || key;
    const baseFlagsUrl = $("#base_flags_url").val()
      ? $("#base_flags_url").val().trim()
      : "";

    $(".date-field").each(function () {
      const $cell = $(this);
      const isoAttr = $cell.data("date-iso");
      const isoDateStr =
        typeof isoAttr !== "undefined" &&
        isoAttr !== null &&
        String(isoAttr).trim() !== ""
          ? String(isoAttr).trim()
          : $cell.text().trim();

      if (!isoDateStr || isoDateStr === "N/A") return;

      const date = new Date(isoDateStr);

      if (!Number.isNaN(date)) {
        $cell.text(date.toLocaleString());
      } else {
        console.error(`Invalid date string: ${isoDateStr}`);
      }
    });

    $(".table").each(function () {
      const $table = $(this);
      const tableKey = ($table.data("table-key") || "").toString();
      const normalizedTableKey = tableKey.toLowerCase();
      const tableId = this.id;
      let tableLength = parseInt($(`#${tableId}-length`).val().trim(), 10);
      if (Number.isNaN(tableLength)) {
        tableLength = 0;
      }

      var tableOrder;
      const $tableOrder = $(`#${tableId}-order`);
      if ($tableOrder.length) {
        tableOrder = JSON.parse($tableOrder.text().trim());
      } else {
        tableOrder = { column: 0, dir: "desc" };
      }

      var tableTypes;
      const $tableTypes = $(`#${tableId}-types`);
      if ($tableTypes.length) {
        tableTypes = JSON.parse($tableTypes.text().trim());
      }

      const layout = {
        top1: {},
        topStart: {},
        topEnd: {},
        bottomStart: {},
        bottomEnd: {},
      };

      if (tableLength > 10) {
        const menu = [10];
        if (tableLength > 25) {
          menu.push(25);
        }
        if (tableLength > 50) {
          menu.push(50);
        }
        if (tableLength > 100) {
          menu.push(100);
        }
        menu.push({ label: "All", value: -1 });
        layout.topStart.pageLength = {
          menu: menu,
        };
        layout.bottomEnd.paging = true;
      }

      const columnDefs = [];
      const columnCount = $table.find("thead th").length;
      if (tableTypes) {
        Object.entries(tableTypes).forEach(([column, type]) => {
          columnDefs.push({
            type: type,
            targets: parseInt(column),
          });
        });
      }

      const columnNameToIndex = {};
      $table.find("thead th").each(function (index) {
        const headerText = $(this)
          .text()
          .trim()
          .toLowerCase()
          .replace(/\s+/g, "_");
        columnNameToIndex[headerText] = index;
      });

      const isHistoryTable =
        normalizedTableKey === "list_bad_behavior_history" ||
        tableId.includes("list-bad-behavior-history");
      let searchPaneColumns = [];
      if (isHistoryTable) {
        const paneTargets = [];
        const paneDefs = [
          {
            matchKeys: ["date"],
            headerKey: "searchpane.date",
            fallback: "Date",
          },
          {
            matchKeys: ["ip", "ip_address"],
            headerKey: "searchpane.ip_address",
            fallback: "IP Address",
          },
          {
            matchKeys: ["country"],
            headerKey: "searchpane.country",
            fallback: "Country",
          },
          {
            matchKeys: ["server_name", "server"],
            headerKey: "searchpane.server_name",
            fallback: "Server",
          },
          {
            matchKeys: ["method"],
            headerKey: "searchpane.method",
            fallback: "Method",
          },
          {
            matchKeys: ["url"],
            headerKey: "searchpane.url",
            fallback: "URL",
          },
          {
            matchKeys: ["status", "status_code"],
            headerKey: "searchpane.status_code",
            fallback: "Status Code",
          },
          {
            matchKeys: ["security_mode"],
            headerKey: "searchpane.security_mode",
            fallback: "Security Mode",
          },
          {
            matchKeys: ["ban_scope"],
            headerKey: "searchpane.ban_scope",
            fallback: "Ban Scope",
          },
        ];

        paneDefs.forEach(({ matchKeys, headerKey, fallback }) => {
          const targetIndex = matchKeys
            .map((key) => columnNameToIndex[key])
            .find((value) => value !== undefined);
          if (targetIndex !== undefined && targetIndex < columnCount) {
            paneTargets.push(targetIndex);
            const columnDef = {
              searchPanes: {
                show: true,
                header: t(headerKey, fallback),
                combiner: "or",
              },
              targets: targetIndex,
            };

            if (headerKey === "searchpane.country") {
              columnDef.render = function (data, type) {
                const rawValue = (data || "").toString().trim();
                const normalizedCode = rawValue
                  ? rawValue.toLowerCase()
                  : "unknown";
                const isLocal =
                  normalizedCode === "local" || normalizedCode === "unknown";
                const flagCode = isLocal ? "zz" : normalizedCode;
                const label = isLocal
                  ? t("country.not_applicable", "N/A")
                  : rawValue.toUpperCase();
                if (type === "display") {
                  return `
                    <span data-bs-toggle="tooltip" data-country="${escapeHtml(
                      isLocal ? "unknown" : normalizedCode.toUpperCase(),
                    )}" data-bs-original-title="${escapeHtml(label)}">
                      <img src="${escapeHtml(baseFlagsUrl)}/${escapeHtml(
                        flagCode,
                      )}.svg" class="border border-1 p-0 me-1" height="17" loading="lazy" />
                      &nbsp;－&nbsp;${escapeHtml(isLocal ? "N/A" : rawValue)}
                    </span>`;
                }
                return isLocal ? "N/A" : rawValue;
              };
            }

            columnDefs.push(columnDef);
          }
        });

        searchPaneColumns = paneTargets;
        layout.top1.searchPanes = {
          viewTotal: true,
          cascadePanes: true,
          collapse: false,
          columns: searchPaneColumns,
        };
        layout.topEnd = layout.topEnd || {};
        layout.topEnd.search = true;
        const hasToggleButton =
          layout.topEnd.buttons &&
          layout.topEnd.buttons.some((btn) => btn.extend === "toggle_filters");
        if (!hasToggleButton) {
          layout.topEnd.buttons = [
            ...(layout.topEnd.buttons || []),
            {
              extend: "toggle_filters",
              className: "btn btn-sm btn-outline-primary toggle-filters",
            },
          ];
        }
        layout.bottomStart = layout.bottomStart || {};
        layout.bottomStart.info = true;
      }

      initializeDataTable({
        tableSelector: this,
        tableName: tableKey || tableId,
        columnVisibilityCondition: (column) => false, // Ignore all columns
        dataTableOptions: {
          columnDefs: columnDefs,
          autoFill: false,
          responsive: true,
          layout: layout,
          order: [[parseInt(tableOrder.column), tableOrder.dir]],
          searchPanes:
            searchPaneColumns.length > 0
              ? {
                  cascadePanes: true,
                  viewTotal: true,
                  collapse: false,
                  columns: searchPaneColumns,
                }
              : undefined,
        },
      });

      $table.removeClass("d-none");
    });

    $(".dt-type-numeric").removeClass("dt-type-numeric");
  });
})();
