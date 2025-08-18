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
      title: "Request ID",
      tooltip: "The unique identifier for the request",
      i18n: "tooltip.table.reports.request_id",
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
        columns: [3, 4, 5, 6, 7, 9, 10, 12],
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
      columns: "th:not(:nth-child(-n+2))",
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
    columnVisibilityCondition: (column) => column > 1 && column < 13,
    dataTableOptions: {
      columnDefs: [
        { orderable: false, targets: -1 },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.ip_address", "IP Address"),
            combiner: "or",
          },
          type: "ip-address",
          targets: 3,
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
          targets: 4,
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
                <img src="${escapeHtml(baseFlagsUrl)}/${
                  countryCode === "local" ? "zz" : escapeHtml(countryCode)
                }.svg"
                     class="border border-1 p-0 me-1"
                     height="17"
                     loading="lazy" />
                &nbsp;－&nbsp;${
                  countryCode === "local" ? "N/A" : escapeHtml(data)
                }
              </span>`;
          },
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.ip_address", "IP Address"),
            combiner: "or",
          },
          targets: 3,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.method", "Method"),
            combiner: "or",
          },
          targets: 5,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.url", "URL"),
            combiner: "or",
          },
          targets: 6,
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
                          data-bs-placement="top"
                          data-i18n="tooltip.view_full_url"><a href="#"
                          class="text-truncate url-truncated text-decoration-underline"
                          data-bs-toggle="modal"
                          data-bs-target="#fullUrlModal"
                          data-url="${data}"
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
            header: t("searchpane.status_code", "Status Code"),
            combiner: "or",
          },
          targets: 7,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.reason", "Reason"),
            combiner: "or",
          },
          targets: 9,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.server_name", "Server name"),
            combiner: "or",
          },
          targets: 10,
          render: function (data) {
            return data === "_"
              ? `<span data-i18n="status.default_server">default server</span>`
              : data;
          },
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.data", "Data"),
            combiner: "or",
          },
          targets: 11,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.security_mode", "Security mode"),
            combiner: "or",
          },
          targets: 12,
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
            .removeClass("visually-hidden")
            .addClass("text-danger")
            .text(
              t(
                "error.reports_load_error",
                "Error loading reports. Please try refreshing the page.",
              ),
            );
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
          data: "id",
          title: "<span data-i18n='table.header.request_id'>Request ID</span>",
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
            if (type === "display") {
              try {
                // Try to parse the data as JSON if it's a string
                const jsonData =
                  typeof data === "string" ? JSON.parse(data) : data;

                // Check if there's meaningful data to display
                if (jsonData && Object.keys(jsonData).length > 0) {
                  // Safely encode the data, with fallback for encoding issues
                  let encodedData;
                  try {
                    encodedData = encodeURIComponent(JSON.stringify(jsonData));
                  } catch (encodeError) {
                    console.warn(
                      "Failed to encode data for modal, using fallback:",
                      encodeError,
                    );
                    // Store raw data as base64 as ultimate fallback
                    encodedData = btoa(JSON.stringify(jsonData || {}));
                  }

                  return `<a href="#"
                            class="text-decoration-underline"
                            data-bs-toggle="modal"
                            data-bs-target="#dataModal"
                            data-report-data="${escapeHtmlAttribute(
                              encodedData,
                            )}"
                            data-raw-data="${escapeHtmlAttribute(
                              JSON.stringify(jsonData),
                            )}"
                            style="cursor: pointer;"
                            data-i18n="button.view_details">
                            ${t("button.view_details", "View Details")}
                          </a>`;
                } else {
                  return `<span data-i18n="status.no_data">No data</span>`;
                }
              } catch (e) {
                console.warn("Error parsing data JSON:", e);
                // Even if parsing fails, provide a way to access the raw data
                const safeData =
                  typeof data === "string" ? data : String(data || "No data");
                const fallbackData = JSON.stringify({
                  error: "Parse error",
                  raw: safeData,
                });
                return `<a href="#"
                          class="text-decoration-underline"
                          data-bs-toggle="modal"
                          data-bs-target="#dataModal"
                          data-report-data="${escapeHtmlAttribute(
                            encodeURIComponent(fallbackData),
                          )}"
                          data-raw-data="${escapeHtmlAttribute(safeData)}"
                          style="cursor: pointer;"
                          data-i18n="button.view_raw_data">
                          ${t("button.view_raw_data", "View Raw Data")}
                        </a>`;
              }
            } else if (type === "filter") {
              try {
                const jsonData =
                  typeof data === "string" ? JSON.parse(data) : data;
                return JSON.stringify(jsonData);
              } catch (e) {
                return typeof data === "string" ? data : String(data || "");
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

  // Add a fallback timeout to prevent infinite loading
  setTimeout(function () {
    if ($("#reports").hasClass("d-none")) {
      $("#reports-waiting")
        .removeClass("visually-hidden")
        .addClass("text-danger")
        .text(
          t(
            "error.reports_load_error",
            "Error loading reports. Please try refreshing the page.",
          ),
        );
      $("#reports").addClass("d-none");
    }
  }, 5000); // 5 seconds fallback

  // Add copy functionality to the copy button
  $(document).on("click", "#copyUrlBtn", function () {
    const textToCopy = $("#fullUrlContent").text();
    navigator.clipboard.writeText(textToCopy).then(() => {
      // Change button text temporarily to indicate success
      const $btn = $(this);
      const originalHtml = $btn.html();
      $btn.html(
        '<span class="tf-icons bx bx-check me-1"></span><span data-i18n="toast.copied">Copied!</span>',
      );
      setTimeout(() => {
        $btn.html(originalHtml);
      }, 2000);
    });
  });

  // Add copy functionality for data modal
  $(document).on("click", "#copyDataBtn", function () {
    try {
      const rawData = $("#dataModal").data("raw-data");
      let textToCopy;

      if (rawData !== null && rawData !== undefined) {
        if (typeof rawData === "object") {
          try {
            textToCopy = JSON.stringify(rawData, null, 2);
          } catch (jsonError) {
            console.warn(
              "Failed to stringify raw data, using string conversion:",
              jsonError,
            );
            textToCopy = String(rawData);
          }
        } else {
          textToCopy = String(rawData);
        }
      } else {
        console.warn("No raw data available in modal");
        textToCopy = "No data available";
      }

      navigator.clipboard
        .writeText(textToCopy)
        .then(() => {
          const $btn = $(this);
          const originalHtml = $btn.html();
          $btn.html(
            '<span class="tf-icons bx bx-check me-1"></span><span data-i18n="toast.copied">Copied!</span>',
          );
          setTimeout(() => {
            $btn.html(originalHtml);
          }, 2000);
        })
        .catch((clipboardError) => {
          console.error("Failed to copy to clipboard:", clipboardError);
          // Fallback: show an alert or try alternative method
          alert(
            "Failed to copy to clipboard. Please try using the raw data copy button below.",
          );
        });
    } catch (e) {
      console.error("Critical error in copy data functionality:", e);
      alert(
        "Error accessing data for copying. Please try refreshing the page.",
      );
    }
  });

  // Update the handler for the modal to display the full URL
  $("#fullUrlModal").on("show.bs.modal", function (event) {
    const button = $(event.relatedTarget); // Button that triggered the modal
    const url = button.data("url"); // Extract URL from data-url attribute
    // Use text() to safely set content without XSS risk
    $("#fullUrlContent").text(url || "No URL available");
  });

  // Handler for the data modal to display formatted security report data
  $("#dataModal").on("show.bs.modal", function (event) {
    const button = $(event.relatedTarget);
    const reportDataString = button.data("report-data");
    let rawDataForFallback = null;
    let reason = "Unknown";
    let anomalyScore = null;
    let isModSec = false;

    try {
      // First, try to get the reason from row data
      const $row = button.closest("tr");
      const table = $("#reports").DataTable();
      const rowData = table.row($row).data();
      if (rowData && rowData.reason) {
        reason = rowData.reason;
      }

      // Try to parse the report data
      let reportData;
      if (reportDataString) {
        try {
          reportData = JSON.parse(decodeURIComponent(reportDataString));
        } catch (parseError) {
          console.warn(
            "Failed to parse report data string, trying direct parsing:",
            parseError,
          );
          try {
            // Try to parse without decoding
            reportData = JSON.parse(reportDataString);
          } catch (directParseError) {
            console.warn(
              "Failed direct parsing, trying base64 decode:",
              directParseError,
            );
            try {
              // Try base64 decode as last resort for encoded data
              const base64Decoded = atob(reportDataString);
              reportData = JSON.parse(base64Decoded);
            } catch (base64Error) {
              console.warn(
                "All parsing methods failed, using fallback:",
                base64Error,
              );
              // Create a fallback object with the original data
              reportData = {
                error: "Parsing failed",
                raw: reportDataString,
                note: "Raw data preserved for access",
              };
            }
          }
        }
      } else {
        // If no report data string, try to get raw data from row
        reportData = rowData ? rowData.data : {};
        if (typeof reportData === "string") {
          try {
            reportData = JSON.parse(reportData);
          } catch (rowParseError) {
            console.warn("Failed to parse row data:", rowParseError);
            reportData = {
              error: "Row data parsing failed",
              raw: reportData,
              note: "Raw data preserved for access",
            };
          }
        }
      }

      rawDataForFallback = reportData || {};
      $("#dataModal").data("raw-data", rawDataForFallback);

      // Detect ModSecurity report and extract anomaly score
      if (
        reportData &&
        (reportData.anomaly_score !== undefined ||
          reportData.ids ||
          reportData.msgs)
      ) {
        isModSec = true;
        anomalyScore = reportData.anomaly_score;
      }

      // Update modal title with reason and anomaly score badge if present
      let modalTitleHtml = `
        <span class="tf-icons bx bx-shield-alt-2 me-2"></span>Security Report Details - ${escapeHtml(
          reason,
        )}
      `;
      if (
        isModSec &&
        anomalyScore !== undefined &&
        anomalyScore !== null &&
        anomalyScore !== ""
      ) {
        modalTitleHtml += `<span class="badge bg-danger ms-2 align-middle">Anomaly Score: <span class="fw-bold">${escapeHtml(
          anomalyScore,
        )}</span></span>`;
      }
      $("#dataModalLabel").html(modalTitleHtml);

      // Generate formatted content with error handling
      try {
        const formattedContent = formatSecurityReportData(reportData);
        $("#dataContent").html(formattedContent);
      } catch (formatError) {
        console.error("Error formatting report data:", formatError);
        // Show raw data as fallback when formatting fails
        const rawDataDisplay = createRawDataFallback(rawDataForFallback);
        $("#dataContent").html(`
          <div class="alert alert-warning mb-3">
            <span class="tf-icons bx bx-error-circle me-1"></span>
            Unable to format data properly. Showing raw data below:
          </div>
          ${rawDataDisplay}
        `);
      }
    } catch (e) {
      console.error("Critical error in data modal:", e);

      // Try to get raw data from the original row as ultimate fallback
      try {
        const $row = button.closest("tr");
        const table = $("#reports").DataTable();
        const rowData = table.row($row).data();
        if (rowData && rowData.data) {
          rawDataForFallback =
            typeof rowData.data === "string"
              ? JSON.parse(rowData.data)
              : rowData.data;
        } else {
          rawDataForFallback = {
            error: "No data available",
            original: reportDataString || "undefined",
          };
        }
      } catch (fallbackError) {
        console.error("Even fallback failed:", fallbackError);
        rawDataForFallback = {
          error: "Data parsing failed completely",
          original: reportDataString || "undefined",
          errorMessage: e.message,
        };
      }

      // Ensure raw data is always available for copy
      $("#dataModal").data("raw-data", rawDataForFallback);

      $("#dataModalLabel").html(`
        <span class="tf-icons bx bx-shield-alt-2 me-2"></span>Security Report Details - ${escapeHtml(
          reason,
        )}
      `);

      // Show error message with raw data access
      const rawDataDisplay = createRawDataFallback(rawDataForFallback);
      $("#dataContent").html(`
        <div class="alert alert-danger mb-3">
          <span class="tf-icons bx bx-error-circle me-1"></span>
          Error processing report data. Raw data is available below for copying:
        </div>
        ${rawDataDisplay}
      `);
    }
  });

  // Function to safely escape HTML content
  function escapeHtml(text) {
    if (typeof text !== "string") {
      text = String(text);
    }
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Function to safely escape HTML attributes (more restrictive)
  function escapeHtmlAttribute(text) {
    if (typeof text !== "string") {
      text = String(text);
    }
    return text
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\//g, "&#x2F;");
  }

  // Function to create raw data fallback display
  function createRawDataFallback(data) {
    try {
      const jsonString = JSON.stringify(data, null, 2);
      return `
        <div class="raw-data-container">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <small class="text-muted">Raw Data (JSON format):</small>
            <button type="button" class="btn btn-sm btn-outline-secondary" onclick="copyRawDataToClipboard(this)">
              <span class="tf-icons bx bx-copy me-1"></span><span data-i18n="button.copy_raw">Copy Raw Data</span>
            </button>
          </div>
          <pre class="p-3 bg-light border rounded small" style="max-height: 300px; overflow-y: auto;"><code>${escapeHtml(
            jsonString,
          )}</code></pre>
        </div>
      `;
    } catch (e) {
      // Even JSON.stringify failed, show the raw object/string as is
      const fallbackContent = typeof data === "object" ? String(data) : data;
      return `
        <div class="raw-data-container">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <small class="text-muted">Raw Data (string format):</small>
            <button type="button" class="btn btn-sm btn-outline-secondary" onclick="copyRawDataToClipboard(this)">
              <span class="tf-icons bx bx-copy me-1"></span><span data-i18n="button.copy_raw">Copy Raw Data</span>
            </button>
          </div>
          <pre class="p-3 bg-light border rounded small" style="max-height: 300px; overflow-y: auto;"><code>${escapeHtml(
            String(fallbackContent),
          )}</code></pre>
        </div>
      `;
    }
  }

  // Global function to copy raw data to clipboard from fallback display
  window.copyRawDataToClipboard = function (button) {
    try {
      const rawData = $("#dataModal").data("raw-data");
      let textToCopy;

      if (rawData !== null && rawData !== undefined) {
        if (typeof rawData === "object") {
          textToCopy = JSON.stringify(rawData, null, 2);
        } else {
          textToCopy = String(rawData);
        }
      } else {
        textToCopy = "No data available";
      }

      navigator.clipboard
        .writeText(textToCopy)
        .then(() => {
          const $btn = $(button);
          const originalHtml = $btn.html();
          $btn.html(
            '<span class="tf-icons bx bx-check me-1"></span><span data-i18n="toast.copied">Copied!</span>',
          );
          setTimeout(() => {
            $btn.html(originalHtml);
          }, 2000);
        })
        .catch((err) => {
          console.error("Failed to copy to clipboard:", err);
          // Fallback: select the text for manual copying
          const preElement = $(button)
            .closest(".raw-data-container")
            .find("pre")[0];
          if (preElement) {
            const range = document.createRange();
            range.selectNodeContents(preElement);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
          }
        });
    } catch (e) {
      console.error("Error copying raw data:", e);
    }
  };

  // Function to format security report data
  function formatSecurityReportData(data) {
    if (!data || typeof data !== "object") {
      return '<div class="alert alert-warning" data-i18n="status.no_data">No data available</div>';
    }

    let html = "";

    // Check if this looks like a ModSecurity-style report
    const hasSecurityFields =
      data.ids ||
      data.msgs ||
      data.matched_var_names ||
      data.matched_vars ||
      data.anomaly_score;

    if (hasSecurityFields) {
      html += formatModSecurityData(data);
    } else {
      html += formatGenericData(data);
    }

    return html;
  }

  // Function to format ModSecurity-style data
  function formatModSecurityData(data) {
    const ids = data.ids || [];
    const msgs = data.msgs || [];
    const varNames = data.matched_var_names || [];
    const varValues = data.matched_vars || [];

    // Group related items by index
    const maxLength = Math.max(
      ids.length,
      msgs.length,
      varNames.length,
      varValues.length,
    );

    if (maxLength === 0) {
      return '<div class="alert alert-info" data-i18n="status.no_data">No security data available</div>';
    }

    let html = '<div class="security-report-data">';

    for (let i = 0; i < maxLength; i++) {
      html += `<div class="security-incident mb-4 p-3 border rounded">`;
      html += `<h6 class="text-primary mb-3"><span class="tf-icons bx bx-error-circle me-1"></span><span data-i18n="reports.security_incident">Security Incident</span> ${
        i + 1
      }</h6>`;

      if (ids[i]) {
        html += `<div class="mb-2">
          <strong class="text-muted">Rule ID:</strong>
          <span class="badge bg-secondary ms-1">${escapeHtml(ids[i])}</span>
        </div>`;
      }

      if (msgs[i]) {
        html += `<div class="mb-2">
          <strong class="text-muted">Message:</strong>
          <span class="ms-1">${escapeHtml(msgs[i])}</span>
        </div>`;
      }

      if (varNames[i]) {
        html += `<div class="mb-2">
          <strong class="text-muted">Variable:</strong>
          <code class="ms-1">${escapeHtml(varNames[i])}</code>
        </div>`;
      }

      if (varValues[i]) {
        html += `<div class="mb-2">
          <strong class="text-muted">Value:</strong>
          <code class="ms-1 text-break">${escapeHtml(varValues[i])}</code>
        </div>`;
      }

      html += "</div>";
    }

    html += "</div>";
    return html;
  }

  // Function to format generic data
  function formatGenericData(data) {
    let html = '<div class="generic-report-data">';

    // Check if this might be a structured security report
    const securityKeys = [
      "rule",
      "reason",
      "matched",
      "blocked",
      "detected",
      "pattern",
      "signature",
    ];
    const hasSecurityContext = Object.keys(data).some((key) =>
      securityKeys.some((secKey) => key.toLowerCase().includes(secKey)),
    );

    if (hasSecurityContext) {
      html +=
        '<div class="alert alert-info mb-3"><span class="tf-icons bx bx-info-circle me-1"></span><span data-i18n="reports.security_report_data">Security Report Data</span></div>';
    }

    for (const [key, value] of Object.entries(data)) {
      html += `<div class="mb-3 ${
        hasSecurityContext ? "security-field" : ""
      }">`;

      // Make key more readable
      const displayKey = key
        .replace(/_/g, " ")
        .replace(/([A-Z])/g, " $1")
        .trim();
      const capitalizedKey =
        displayKey.charAt(0).toUpperCase() + displayKey.slice(1);

      html += `<strong class="text-muted">${escapeHtml(
        capitalizedKey,
      )}:</strong>`;

      if (Array.isArray(value)) {
        if (value.length === 0) {
          html += `<span class="ms-1 text-muted" data-i18n="status.no_data">No items</span>`;
        } else {
          html += `<ul class="mt-1 mb-0">`;
          value.forEach((item, index) => {
            if (typeof item === "object") {
              html += `<li><pre class="mb-1 p-1 bg-light border rounded small"><code>${escapeHtml(
                JSON.stringify(item, null, 2),
              )}</code></pre></li>`;
            } else {
              html += `<li><code class="text-break">${escapeHtml(
                String(item),
              )}</code></li>`;
            }
          });
          html += `</ul>`;
        }
      } else if (typeof value === "object" && value !== null) {
        html += `<pre class="mt-1 p-2 bg-light border rounded small"><code>${escapeHtml(
          JSON.stringify(value, null, 2),
        )}</code></pre>`;
      } else {
        // Handle different value types with appropriate styling
        const stringValue = String(value);
        if (stringValue.length > 100) {
          html += `<div class="mt-1"><code class="text-break">${escapeHtml(
            stringValue,
          )}</code></div>`;
        } else if (
          key.toLowerCase().includes("id") ||
          key.toLowerCase().includes("code")
        ) {
          html += `<span class="ms-1"><span class="badge bg-secondary">${escapeHtml(
            stringValue,
          )}</span></span>`;
        } else {
          html += `<span class="ms-1"><code>${escapeHtml(
            stringValue,
          )}</code></span>`;
        }
      }

      html += `</div>`;
    }

    html += "</div>";
    return html;
  }

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
        // Hide waiting message and show table
        $("#reports-waiting").addClass("visually-hidden");
        $("#reports").removeClass("d-none");
      });
      // Ensure tooltips are set after initialization
      updateHeaderTooltips(dt.table().header(), headers);
      $("#reports_wrapper").find(".btn-secondary").removeClass("btn-secondary");
      // Hide waiting message and show table
      $("#reports-waiting").addClass("visually-hidden");
      $("#reports").removeClass("d-none");
      return dt;
    });
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
});
