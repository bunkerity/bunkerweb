$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key; // Fallback
  const baseFlagsUrl = $("#base_flags_url").val().trim();

  const headers = [
    {
      title: "Date",
      tooltip: "The date and time when the Report was created",
      i18n: "tooltip.table.reports.date",
    },
    {
      title: "IP Address",
      tooltip: "The reported IP address",
      i18n: "tooltip.table.reports.ip_address",
    },
    {
      title: "Country",
      tooltip: "The country of the reported IP address",
      i18n: "tooltip.table.reports.country",
    },
    {
      title: "Method",
      tooltip: "The method used by the attacker",
      i18n: "tooltip.table.reports.method",
    },
    {
      title: "URL",
      tooltip: "The URL that was targeted by the attacker",
      i18n: "tooltip.table.reports.url",
    },
    {
      title: "Status Code",
      tooltip: "The HTTP status code returned by BunkerWeb",
      i18n: "tooltip.table.reports.status_code",
    },
    {
      title: "User-Agent",
      tooltip: "The User-Agent of the attacker",
      i18n: "tooltip.table.reports.user_agent",
    },
    {
      title: "Reason",
      tooltip: "The reason why the Report was created",
      i18n: "tooltip.table.reports.reason",
    },
    {
      title: "Server name",
      tooltip: "The Server name that created the report",
      i18n: "tooltip.table.reports.server_name",
    },
    {
      title: "Data",
      tooltip: "Additional data about the Report",
      i18n: "tooltip.table.reports.data",
    },
    {
      title: "Security mode",
      tooltip: "Security mode",
      i18n: "tooltip.table.reports.security_mode",
    },
  ];

  // Batch update tooltips
  const updateCountryTooltips = () => {
    $("[data-country]").each(function () {
      const $elem = $(this);
      const countryCode = $elem.data("country");

      const countryName = t(
        countryCode === "unknown"
          ? "country.not_applicable"
          : `country.${countryCode}`,
        "Unknown",
      );
      if (countryName && countryName !== "country.not_applicable") {
        $elem.attr("data-bs-original-title", countryName);
      }
    });
    $('[data-bs-toggle="tooltip"]').tooltip("dispose").tooltip();
  };

  // Configure DataTable layout
  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [2, 3, 4, 5, 6, 8, 9, 11],
      },
    },
    topStart: {},
    topEnd: {
      search: true,
      buttons: [
        {
          extend: "auto_refresh",
          className: "btn btn-sm btn-outline-primary d-flex align-items-center",
        },
        {
          extend: "toggle_filters",
          className: "btn btn-sm btn-outline-primary toggle-filters",
        },
      ],
    },
    bottomStart: {
      pageLength: {
        menu: [10, 25, 50, 100, { label: "All", value: -1 }],
      },
      info: true,
    },
  };

  // Define DataTable buttons
  layout.topStart.buttons = [
    {
      extend: "colvis",
      columns: "th:not(:nth-child(-n+3))",
      text: `<span class="tf-icons bx bx-columns bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.columns">${t(
        "button.columns",
        "Columns",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary rounded-start",
      columnText: function (dt, idx, title) {
        const headerCell = dt.column(idx).header();
        const $header = $(headerCell);
        const $translatableElement = $header.find("[data-i18n]");
        let i18nKey = $translatableElement.data("i18n");
        let translatedTitle = title;
        if (i18nKey) {
          translatedTitle = t(i18nKey, title);
        } else {
          translatedTitle = $header.text().trim() || title;
        }
        return `${idx + 1}. <span data-i18n="${
          i18nKey || ""
        }">${translatedTitle}</span>`;
      },
    },
    {
      extend: "colvisRestore",
      text: `<span class="tf-icons bx bx-reset bx-18px me-2"></span><span class="d-none d-md-inline" data-i18n="button.reset_columns">${t(
        "button.reset_columns",
        "Reset columns",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary d-none d-md-inline",
    },
    {
      extend: "collection",
      text: `<span class="tf-icons bx bx-export bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.export">${t(
        "button.export",
        "Export",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary",
      buttons: [
        {
          extend: "copy",
          text: `<span class="tf-icons bx bx-copy bx-18px me-2"></span><span data-i18n="button.copy_visible">${t(
            "button.copy_visible",
            "Copy visible",
          )}</span>`,
          exportOptions: {
            columns: ":visible:not(:first-child)",
          },
        },
        {
          extend: "csv",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV',
          bom: true,
          filename: "bw_report",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:first-child)",
          },
        },
        {
          extend: "excel",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel',
          filename: "bw_report",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:first-child)",
          },
        },
      ],
    },
  ];

  // Custom button for auto-refresh
  let autoRefresh = false;
  const sessionAutoRefresh = sessionStorage.getItem("reportsAutoRefresh");

  function toggleAutoRefresh() {
    autoRefresh = !autoRefresh;
    sessionStorage.setItem("reportsAutoRefresh", autoRefresh);
    if (autoRefresh) {
      $(".bx-loader")
        .addClass("bx-spin")
        .closest(".btn")
        .removeClass("btn-outline-primary")
        .addClass("btn-primary");
      const interval = setInterval(() => {
        if (!autoRefresh) {
          clearInterval(interval);
        } else {
          $("#reports").DataTable().ajax.reload(null, false);
        }
      }, 10000); // 10 seconds
    } else {
      $(".bx-loader")
        .removeClass("bx-spin")
        .closest(".btn")
        .removeClass("btn-primary")
        .addClass("btn-outline-primary");
    }
  }

  $.fn.dataTable.ext.buttons.auto_refresh = {
    text: '<span class="bx bx-loader bx-18px lh-1"></span>&nbsp;&nbsp;<span data-i18n="button.auto_refresh">Auto refresh</span>',
    action: (e, dt, node, config) => {
      toggleAutoRefresh();
    },
  };

  // Initialize DataTable
  const reports_config = {
    tableSelector: "#reports",
    tableName: "reports",
    columnVisibilityCondition: (column) => column > 2 && column < 12,
    dataTableOptions: {
      columnDefs: [
        { orderable: false, targets: -1 },
        { visible: false, targets: [4, 5, 6, 7, 10] },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.ip_address", "IP Address"),
            combiner: "or",
          },
          type: "ip-address",
          targets: 2,
        },
        {
          render: function (data, type, row) {
            if (type === "display" || type === "filter") {
              const date = new Date(data);
              if (!isNaN(date.getTime())) {
                return date.toLocaleString();
              }
            }
            return data;
          },
          targets: 1,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.country", "Country"),
            combiner: "or",
          },
          targets: 3,
          render: function (data) {
            const countryCode = data.toLowerCase();
            const tooltipContent = "N/A";
            return `
              <span data-bs-toggle="tooltip" data-bs-original-title="${tooltipContent}" data-i18n="country.${
                countryCode === "local"
                  ? "not_applicable"
                  : countryCode.toUpperCase()
              }" data-country="${
                countryCode === "local" ? "unknown" : countryCode.toUpperCase()
              }">
                <img src="${baseFlagsUrl}/${
                  countryCode === "local" ? "zz" : countryCode
                }.svg"
                     class="border border-1 p-0 me-1"
                     height="17"
                     loading="lazy" />
                &nbsp;－&nbsp;${countryCode === "local" ? "N/A" : data}
              </span>`;
          },
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.url", "URL"),
            combiner: "or",
          },
          targets: 5,
          render: function (data, type, row) {
            if (type !== "display") {
              return data;
            }

            // For display, check if URL is too long
            const maxUrlLength = 30;
            if (data && data.length > maxUrlLength) {
              // Create shortened version with ellipsis
              const shortUrl = data.substring(0, maxUrlLength - 3) + "...";
              return `<div data-bs-toggle="tooltip"
                        title="Click to view full URL"
                        data-bs-placement="top"><a href="#"
                        class="text-truncate url-truncated text-decoration-underline"
                        data-bs-toggle="modal"
                        data-bs-target="#fullUrlModal"
                        data-url="${data.replace(/"/g, "&quot;")}"
                        style="cursor: pointer;">
                        ${shortUrl}
                      </a></div>`;
            }

            return data;
          },
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.server_name", "Server name"),
            combiner: "or",
          },
          targets: 9,
          render: function (data) {
            return data === "_" ? "default server" : data;
          },
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.ip_address", "IP Address"),
            combiner: "or",
          },
          targets: 2,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.method", "Method"),
            combiner: "or",
          },
          targets: 4,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.url", "URL"),
            combiner: "or",
          },
          targets: 5,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.status_code", "Status Code"),
            combiner: "or",
          },
          targets: 6,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.reason", "Reason"),
            combiner: "or",
          },
          targets: 8,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.server_name", "Server name"),
            combiner: "or",
          },
          targets: 9,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.data", "Data"),
            combiner: "or",
          },
          targets: 10,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.security_mode", "Security mode"),
            combiner: "or",
          },
          targets: 11,
        },
      ],
      order: [[1, "desc"]],
      autoFill: false,
      responsive: true,
      layout: layout,
      processing: true,
      serverSide: true,
      ajax: {
        url: `${window.location.pathname}/fetch`,
        type: "POST",
        data: function (d) {
          d.csrf_token = $("#csrf_token").val(); // Add CSRF token if needed
          return d;
        },
        // Add error handling for ajax requests
        error: function (jqXHR, textStatus, errorThrown) {
          console.error("DataTables AJAX error:", textStatus, errorThrown);
          $("#reports").addClass("d-none");
          $("#reports-waiting")
            .removeClass("d-none")
            .text("Error loading reports. Please try refreshing the page.")
            .addClass("text-danger");
          // Remove any loading indicators
          $(".dataTables_processing").hide();
        },
      },
      columns: [
        {
          data: null,
          defaultContent: "",
          orderable: false,
          className: "dtr-control",
        },
        {
          data: "date",
          title: "<span data-i18n='table.header.date'>Date</span>",
        },
        {
          data: "ip",
          title: "<span data-i18n='table.header.ip_address'>IP Address</span>",
        },
        {
          data: "country",
          title: "<span data-i18n='table.header.country'>Country</span>",
        },
        {
          data: "method",
          title: "<span data-i18n='table.header.method'>Method</span>",
        },
        { data: "url", title: "<span data-i18n='table.header.url'>URL</span>" },
        {
          data: "status",
          title:
            "<span data-i18n='table.header.status_code'>Status Code</span>",
        },
        {
          data: "user_agent",
          title: "<span data-i18n='table.header.user_agent'>User-Agent</span>",
        },
        {
          data: "reason",
          title: "<span data-i18n='table.header.reason'>Reason</span>",
        },
        {
          data: "server_name",
          title:
            "<span data-i18n='table.header.server_name'>Server name</span>",
        },
        {
          data: "data",
          title: "<span data-i18n='table.header.data'>Data</span>",
          render: function (data, type, row) {
            if (type === "display" || type === "filter") {
              try {
                // Try to parse the data as JSON if it's a string
                const jsonData =
                  typeof data === "string" ? JSON.parse(data) : data;
                // Format it for display
                return JSON.stringify(jsonData, null, 2);
              } catch (e) {
                console.warn("Error parsing data JSON:", e);
                // Return a safe fallback if parsing fails
                return "{}";
              }
            }
            return data;
          },
        },
        {
          data: "security_mode",
          title:
            "<span data-i18n='table.header.security_mode'>Security mode</span>",
        },
      ],
      headerCallback: function (thead) {
        updateHeaderTooltips(thead, headers);
      },
    },
  };

  // Create the modal for displaying full URLs once at document ready
  $("body").append(`
    <div class="modal fade" id="fullUrlModal" tabindex="-1" aria-labelledby="fullUrlModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="fullUrlModalLabel">Full URL</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <span id="fullUrlContent" class="text-break"></span>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" id="copyUrlBtn" class="btn btn-sm btn-outline-primary me-1">
              <span class="tf-icons bx bx-copy me-1"></span>Copy
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-bs-dismiss="modal">Close</button>
          </div>
        </div>
      </div>
    </div>
  `);

  // Add copy functionality to the copy button
  $(document).on("click", "#copyUrlBtn", function () {
    const textToCopy = $("#fullUrlContent").text();
    navigator.clipboard.writeText(textToCopy).then(() => {
      // Change button text temporarily to indicate success
      const $btn = $(this);
      const originalHtml = $btn.html();
      $btn.html('<span class="tf-icons bx bx-check me-1"></span>Copied!');
      setTimeout(() => {
        $btn.html(originalHtml);
      }, 2000);
    });
  });

  // Update the handler for the modal to display the full URL
  $("#fullUrlModal").on("show.bs.modal", function (event) {
    const button = $(event.relatedTarget); // Button that triggered the modal
    const url = button.data("url"); // Extract URL from data-url attribute
    $("#fullUrlContent").text(url);
  });

  // Wait for window.i18nextReady = true before continuing
  if (typeof window.i18nextReady === "undefined" || !window.i18nextReady) {
    const waitForI18next = (resolve) => {
      if (window.i18nextReady) {
        resolve();
      } else {
        setTimeout(() => waitForI18next(resolve), 50);
      }
    };

    new Promise((resolve) => {
      waitForI18next(resolve);
    }).then(() => {
      const dt = initializeDataTable(reports_config);
      dt.on("column-visibility.dt", function (e, settings, column, state) {
        updateHeaderTooltips(dt.table().header(), headers);
        $(".tooltip").remove();
      });
      dt.on("draw.dt", function () {
        updateCountryTooltips();
        updateHeaderTooltips(dt.table().header(), headers);
        // Clean up any existing tooltips to prevent memory leaks
        $(".tooltip").remove();
      });
      // Ensure tooltips are set after initialization
      updateHeaderTooltips(dt.table().header(), headers);
      $("#reports_wrapper").find(".btn-secondary").removeClass("btn-secondary");
      return dt;
    });
  }

  // Utility function to manage header tooltips
  function updateHeaderTooltips(selector, headers) {
    $(selector)
      .find("th")
      .each((index, element) => {
        const $th = $(element);
        // Try to get the data-i18n attribute from the header's span
        const i18nKey =
          $th.find("[data-i18n]").data("i18n") || $th.data("i18n");
        if (i18nKey) {
          const header = headers.find(
            (h) =>
              h.i18n ===
              i18nKey.replace("table.header.", "tooltip.table.reports."),
          );
          if (header) {
            $th.attr({
              "data-bs-toggle": "tooltip",
              "data-bs-placement": "bottom",
              "data-i18n": header.i18n,
              title: header.tooltip,
            });
          }
        }
      });
    applyTranslations();
    $('[data-bs-toggle="tooltip"]').tooltip("dispose").tooltip();
  }

  if (sessionAutoRefresh === "true") {
    toggleAutoRefresh();
  }

  const hashValue = location.hash;
  if (hashValue) {
    $("#dt-length-0").val(hashValue.replace("#", ""));
    $("#dt-length-0").trigger("change");
  }

  $("#dt-length-0").on("change", function () {
    const value = $(this).val();
    history.replaceState(
      null,
      "",
      value === "10" ? location.pathname : `#${value}`,
    );
  });
});
