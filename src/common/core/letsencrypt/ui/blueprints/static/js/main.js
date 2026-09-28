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

  $(document).ready(function () {
    // Ensure i18next is loaded before using it
    const t =
      typeof i18next !== "undefined"
        ? i18next.t
        : (key, fallback) => fallback || key; // Fallback

    var actionLock = false;
    const isReadOnly = $("#is-read-only").val()?.trim() === "True";
    const userReadOnly = $("#user-read-only").val()?.trim() === "True";

    // All dynamic HTML interpolations route through DOMPurify before reaching
    // innerHTML. Cert names and account UUIDs are mutable via the renewal-conf
    // basename / inside the conf body — a DB compromise (or any future
    // server-side bug that lets attacker text flow into the cache) would
    // otherwise yield stored XSS in the operator's browser. DOMPurify is
    // loaded globally from src/ui/app/templates/base.html.
    //
    // `sanitizeHtml` strips script tags, event-handler attributes, and any
    // markup that escapes the intended structure. The plain-text variant for
    // attribute values is the same call — DOMPurify's DOMParser-based parsing
    // normalizes whichever attribute-injection payload an attacker tries.
    const sanitizeHtml = (s) => {
      if (typeof DOMPurify === "undefined") {
        // Hard fallback: if DOMPurify failed to load, refuse to render any
        // dynamic markup at all rather than ship raw user input to .html().
        return String(s ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");
      }
      return DOMPurify.sanitize(String(s ?? ""), { ALLOWED_TAGS: ["strong", "em", "code", "a", "br", "p", "ul", "li"], ALLOWED_ATTR: ["href", "data-cert", "class"] });
    };

    // Text-only context (attribute values, plain interpolation in text nodes).
    // Forces ALLOWED_TAGS=[] so no markup survives — pure text content.
    const sanitizeText = (s) => {
      if (typeof DOMPurify === "undefined") {
        return String(s ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");
      }
      return DOMPurify.sanitize(String(s ?? ""), { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
    };

    const headers = [
      {
        title: "Domain",
        tooltip: "Domain name for the certificate",
      },
      {
        title: "Common Name",
        tooltip: "Common Name (CN) in the certificate",
      },
      {
        title: "Issuer",
        tooltip: "Certificate issuing authority",
      },
      {
        title: "Valid From",
        tooltip: "Date from which the certificate is valid",
      },
      {
        title: "Valid To",
        tooltip: "Date until which the certificate is valid",
      },
      {
        title: "Preferred Profile",
        tooltip: "Preferred profile for the certificate",
      },
      {
        title: "Challenge",
        tooltip: "Challenge type used for domain validation",
      },
      {
        title: "Key Type",
        tooltip: "Type of key used in the certificate",
      },
    ];

    // Set up the delete confirmation modal. All dynamic interpolations sanitize
    // the cert name, and the final HTML string is sanitized again at the .html()
    // sink as belt-and-suspenders against any markup that slips past the inner
    // sanitization (e.g. via future template changes).
    const setupDeleteCertModal = (certs) => {
      const $modalBody = $("#deleteCertContent");
      $modalBody.empty();

      if (certs.length === 1) {
        $modalBody.html(
          sanitizeHtml(`<p>You are about to delete the certificate for: <strong>${sanitizeText(certs[0].domain)}</strong></p>`)
        );
        $("#confirmDeleteCertBtn").data("cert-name", certs[0].domain);
      } else {
        const certList = certs
          .map((cert) => `<li>${sanitizeText(cert.domain)}</li>`)
          .join("");
        $modalBody.html(
          sanitizeHtml(`<p>You are about to delete these certificates:</p><ul>${certList}</ul>`)
        );
        $("#confirmDeleteCertBtn").data(
          "cert-names",
          certs.map((c) => c.domain)
        );
      }
    };

    // Error modal. Title uses `.text()` (string-only context). The message body
    // routes through `.html()`; the SHARED defense — sanitizeHtml at the sink —
    // catches anything callers forgot to escape per-interpolation. Caller is
    // still expected to use `sanitizeText` for embedded dynamic values; this is
    // belt-and-suspenders.
    const showErrorModal = (title, message) => {
      $("#errorModalLabel").text(title);
      $("#errorModalContent").html(sanitizeHtml(message));
      const errorModal = new bootstrap.Modal(document.getElementById("errorModal"));
      errorModal.show();
    };

    // Handle delete button click
    $("#confirmDeleteCertBtn").on("click", function () {
      const certName = $(this).data("cert-name");
      const certNames = $(this).data("cert-names");

      if (certName) {
        // Delete single certificate
        deleteCertificate(certName);
      } else if (certNames && Array.isArray(certNames)) {
        // Delete multiple certificates one by one
        const deleteNext = (index) => {
          if (index < certNames.length) {
            deleteCertificate(certNames[index], () => {
              deleteNext(index + 1);
            });
          } else {
            // All deleted, close modal and reload table
            $("#deleteCertModal").modal("hide");
            $("#letsencrypt").DataTable().ajax.reload();
          }
        };
        deleteNext(0);
      }

      // Hide modal after starting delete process
      $("#deleteCertModal").modal("hide");
    });

    // ----- Per-row quick actions -----
    // Delegated click handlers wired once. DataTables re-renders rows on each
    // ajax.reload() so binding on `document` keeps the handlers live across reloads.
    $(document).on("click", "#letsencrypt tbody .delete-single", function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (isReadOnly) {
        alert(t("alert.readonly_mode", "This action is not allowed in read-only mode."));
        return;
      }
      const certName = $(this).data("cert");
      if (!certName) return;
      setupDeleteCertModal([{ domain: certName }]);
      const modal = new bootstrap.Modal(document.getElementById("deleteCertModal"));
      modal.show();
    });

    $(document).on("click", "#letsencrypt tbody .heal-single", function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (isReadOnly) {
        alert(t("alert.readonly_mode", "This action is not allowed in read-only mode."));
        return;
      }
      const certName = $(this).data("cert");
      if (!certName) return;
      // Inline confirmation — heal is destructive (drops the cert from disk) so it deserves a prompt.
      const msg = t(
        "confirm.heal_cert",
        `Heal orphan certificate "${certName}" by removing it from disk and re-issuing with a fresh ACME account on the next scheduler tick?`
      );
      if (!confirm(msg)) return;
      healCertificate(certName);
    });

    function healCertificate(certName) {
      $.ajax({
        url: `${window.location.pathname}/heal`,
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({ cert_name: certName }),
        headers: { "X-CSRFToken": $("#csrf_token").val() },
        success: function (response) {
          if (response.status === "ok") {
            $("#letsencrypt").DataTable().ajax.reload(null, false);
          } else {
            showErrorModal(
              "Heal Failed",
              `<p>Could not heal certificate <strong>${sanitizeText(certName)}</strong>:</p><p>${sanitizeText(response.message || "Unknown error")}</p>`
            );
          }
        },
        error: function (xhr) {
          const msg = (xhr.responseJSON && xhr.responseJSON.message) || xhr.responseText || "Request failed";
          showErrorModal(
            "Heal Failed",
            `<p>Could not heal certificate <strong>${sanitizeText(certName)}</strong>:</p><p>${sanitizeText(msg)}</p>`
          );
        },
      });
    }

    function deleteCertificate(certName, callback) {
      $.ajax({
        url: `${window.location.pathname}/delete`,
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({ cert_name: certName }),
        headers: {
          "X-CSRFToken": $("#csrf_token").val(),
        },
        success: function (response) {
          if (response.status === "ok") {
            if (callback) {
              callback();
            } else {
              $("#letsencrypt").DataTable().ajax.reload();
            }
          } else {
            // Handle 200 OK but with error in response
            showErrorModal(
              "Certificate Deletion Error",
              `<p>Error deleting certificate <strong>${certName}</strong>:</p><p>${response.message || "Unknown error"}</p>`
            );
            if (callback) callback();
            else $("#letsencrypt").DataTable().ajax.reload();
          }
        },
        error: function (xhr, status, error) {
          console.error("Error deleting certificate:", error, xhr);

          // Create a more detailed error message
          let errorMessage = `<p>Failed to delete certificate <strong>${certName}</strong>:</p>`;

          if (xhr.responseJSON && xhr.responseJSON.message) {
            errorMessage += `<p>${xhr.responseJSON.message}</p>`;
          } else if (xhr.responseText) {
            try {
              const parsedError = JSON.parse(xhr.responseText);
              errorMessage += `<p>${parsedError.message || error}</p>`;
            } catch (e) {
              // If can't parse JSON, use the raw response text if not too large
              if (xhr.responseText.length < 200) {
                errorMessage += `<p>${xhr.responseText}</p>`;
              } else {
                errorMessage += `<p>${error || "Unknown error"}</p>`;
              }
            }
          } else {
            errorMessage += `<p>${error || "Unknown error"}</p>`;
          }

          showErrorModal("Certificate Deletion Failed", errorMessage);

          if (callback) callback();
          else $("#letsencrypt").DataTable().ajax.reload();
        },
      });
    }

    // DataTable Layout and Buttons
    const layout = {
      top1: {
        searchPanes: {
          viewTotal: true,
          cascadePanes: true,
          collapse: false,
          columns: [4, 7, 8, 9], // Issuer, Preferred Profile, Challenge and Key Type
        },
      },
      topStart: {},
      topEnd: {
        search: true,
        buttons: [
          {
            extend: "auto_refresh",
            className:
              "btn btn-sm btn-outline-primary d-flex align-items-center",
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

    layout.topStart.buttons = [
      {
        extend: "colvis",
        columns: "th:not(:nth-child(-n+3)):not(:last-child)",
        text: `<span class="tf-icons bx bx-columns bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.columns">${t(
          "button.columns",
          "Columns"
        )}</span>`,
        className: "btn btn-sm btn-outline-primary rounded-start",
        columnText: function (dt, idx, title) {
          return `${idx + 1}. ${title}`;
        },
      },
      {
        extend: "colvisRestore",
        text: `<span class="tf-icons bx bx-reset bx-18px me-2"></span><span class="d-none d-md-inline" data-i18n="button.reset_columns">${t(
          "button.reset_columns",
          "Reset columns"
        )}</span>`,
        className: "btn btn-sm btn-outline-primary d-none d-md-inline",
      },
      {
        extend: "collection",
        text: `<span class="tf-icons bx bx-export bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.export">${t(
          "button.export",
          "Export"
        )}</span>`,
        className: "btn btn-sm btn-outline-primary",
        buttons: [
          {
            extend: "copy",
            text: `<span class="tf-icons bx bx-copy bx-18px me-2"></span><span data-i18n="button.copy_visible">${t(
              "button.copy_visible",
              "Copy visible"
            )}</span>`,
            exportOptions: {
              columns: ":visible:not(:nth-child(-n+2)):not(:last-child)",
            },
          },
          {
            extend: "csv",
            text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV`,
            bom: true,
            filename: "bw_certificates",
            exportOptions: {
              modifier: { search: "none" },
              columns: ":not(:nth-child(-n+2)):not(:last-child)",
            },
          },
          {
            extend: "excel",
            text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
            filename: "bw_certificates",
            exportOptions: {
              modifier: { search: "none" },
              columns: ":not(:nth-child(-n+2)):not(:last-child)",
            },
          },
        ],
      },
      {
        extend: "collection",
        text: `<span class="tf-icons bx bx-play bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.actions">${t(
          "button.actions",
          "Actions"
        )}</span>`,
        className: "btn btn-sm btn-outline-primary action-button disabled",
        buttons: [{ extend: "delete_cert", className: "text-danger" }],
      },
    ];

    let autoRefresh = false;
    let autoRefreshInterval = null;
    const sessionAutoRefresh = sessionStorage.getItem("letsencryptAutoRefresh");

    function toggleAutoRefresh() {
      autoRefresh = !autoRefresh;
      sessionStorage.setItem("letsencryptAutoRefresh", autoRefresh);
      if (autoRefresh) {
        $(".bx-loader")
          .addClass("bx-spin")
          .closest(".btn")
          .removeClass("btn-outline-primary")
          .addClass("btn-primary");
        if (autoRefreshInterval) clearInterval(autoRefreshInterval);
        autoRefreshInterval = setInterval(() => {
          if (!autoRefresh) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
          } else {
            $("#letsencrypt").DataTable().ajax.reload(null, false);
          }
        }, 10000); // 10 seconds
      } else {
        $(".bx-loader")
          .removeClass("bx-spin")
          .closest(".btn")
          .removeClass("btn-primary")
          .addClass("btn-outline-primary");
        if (autoRefreshInterval) {
          clearInterval(autoRefreshInterval);
          autoRefreshInterval = null;
        }
      }
    }

    if (sessionAutoRefresh === "true") {
      toggleAutoRefresh();
    }

    const getSelectedCertificates = () => {
      const certs = [];
      $("tr.selected").each(function () {
        const $row = $(this);
        const domain = $row.find("td:eq(2)").text().trim();
        certs.push({
          domain: domain,
        });
      });
      return certs;
    };

    $.fn.dataTable.ext.buttons.auto_refresh = {
      text: '<span class="bx bx-loader bx-18px lh-1"></span>&nbsp;&nbsp;<span data-i18n="button.auto_refresh">Auto refresh</span>',
      action: (e, dt, node, config) => {
        toggleAutoRefresh();
      },
    };

    $.fn.dataTable.ext.buttons.delete_cert = {
      text: `<span class="tf-icons bx bx-trash bx-18px me-2"></span>Delete certificate`,
      action: function (e, dt, node, config) {
        if (isReadOnly) {
          alert(
            t(
              "alert.readonly_mode",
              "This action is not allowed in read-only mode."
            )
          );
          return;
        }
        if (actionLock) return;
        actionLock = true;
        $(".dt-button-background").click();

        const certs = getSelectedCertificates();
        if (certs.length === 0) {
          actionLock = false;
          return;
        }
        setupDeleteCertModal(certs);

        // Show the modal
        const deleteModal = new bootstrap.Modal(
          document.getElementById("deleteCertModal")
        );
        deleteModal.show();

        actionLock = false;
      },
    };

    // Per-row quick actions (Delete, Heal orphan). Mirrors the pattern used by
    // src/ui/app/static/js/pages/reports.js (per-row Ban button). Heal button is
    // hidden when the cert is not orphaned (row.is_orphan === false).
    function renderRowActions(data, type, row) {
      if (type !== "display") return "";
      const readOnly = typeof isReadOnly !== "undefined" && isReadOnly;
      const ro = readOnly ? " disabled" : "";
      const roTip = readOnly
        ? t("tooltip.readonly_mode", "This action is not allowed in read-only mode.")
        : "";
      // Every dynamic attribute value is text-only — sanitizeText neutralizes any
      // markup or attribute-breakout payload before the string reaches innerHTML
      // via DataTables. i18n tooltip strings get the same treatment in case a
      // translator embeds `"` or HTML.
      const certName = sanitizeText(row.domain || "");
      const delTip = sanitizeText(roTip || t("tooltip.delete_cert", "Delete this certificate"));
      const healTip = sanitizeText(roTip || t("tooltip.heal_cert", "Heal orphan certificate (re-issue with a fresh ACME account)"));
      const healBtn = row.is_orphan
        ? `<button type="button"
                   class="btn btn-outline-warning btn-sm me-1 heal-single${ro}"
                   data-cert="${certName}"
                   data-bs-toggle="tooltip"
                   data-bs-placement="bottom"
                   data-bs-original-title="${healTip}">
             <i class="bx bx-first-aid bx-xs"></i>
           </button>`
        : "";
      const html = `
        <div class="d-flex justify-content-center">
          ${healBtn}
          <button type="button"
                  class="btn btn-outline-danger btn-sm delete-single${ro}"
                  data-cert="${certName}"
                  data-bs-toggle="tooltip"
                  data-bs-placement="bottom"
                  data-bs-original-title="${delTip}">
            <i class="bx bx-trash bx-xs"></i>
          </button>
        </div>`;
      // Final defense-in-depth: pass the assembled HTML through DOMPurify so any
      // attribute-injection payload that survived sanitizeText (e.g. via locale
      // misconfiguration) gets stripped before it reaches the row.
      return typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(html, { ADD_ATTR: ["data-cert", "data-bs-toggle", "data-bs-placement", "data-bs-original-title"] }) : html;
    }

    // Create columns configuration
    function buildColumnDefs() {
      return [
        { orderable: false, className: "dtr-control", targets: 0 },
        { orderable: false, render: DataTable.render.select(), targets: 1 },
        { type: "string", targets: 2 }, // domain
        { orderable: false, targets: -1, render: renderRowActions },
        {
          targets: [5, 6],
          render: function (data, type, row) {
            if (type === "display" || type === "filter") {
              const date = new Date(data);
              if (!isNaN(date.getTime())) {
                return date.toLocaleString();
              }
            }
            return data;
          },
        },
        {
          searchPanes: {
            show: true,
            combiner: "or",
            header: t("searchpane.issuer", "Issuer"),
          },
          targets: 4, // Issuer column
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.preferred_profile", "Preferred Profile"),
            combiner: "or",
          },
          targets: 7, // Preferred Profile column
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.challenge", "Challenge"),
            combiner: "or",
          },
          targets: 8, // Challenge column
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.key_type", "Key Type"),
            combiner: "or",
          },
          targets: 9, // Key Type column
        },
      ];
    }

    // Define the columns for the DataTable
    function buildColumns() {
      return [
        {
          data: null,
          defaultContent: "",
          orderable: false,
          className: "dtr-control",
        },
        { data: null, defaultContent: "", orderable: false },
        {
          data: "domain",
          title: "Domain",
        },
        {
          data: "common_name",
          title: "Common Name",
        },
        {
          data: "issuer",
          title: "Issuer",
        },
        {
          data: "valid_from",
          title: "Valid From",
        },
        {
          data: "valid_to",
          title: "Valid To",
        },
        {
          data: "preferred_profile",
          title: "Preferred Profile",
        },
        {
          data: "challenge",
          title: "Challenge",
        },
        {
          data: "key_type",
          title: "Key Type",
        },
        {
          data: "serial_number",
          title: "Serial Number",
        },
        {
          data: "fingerprint",
          title: "Fingerprint",
        },
        {
          data: "version",
          title: "Version",
        },
        {
          data: null,
          defaultContent: "",
          orderable: false,
          searchable: false,
          title: "Actions",
        },
      ];
    }

    // Utility function to manage header tooltips
    function updateHeaderTooltips(selector, headers) {
      $(selector)
        .find("th")
        .each((index, element) => {
          const $th = $(element);
          const tooltip = headers[index] ? headers[index].tooltip : "";
          if (!tooltip) return;

          $th.attr({
            "data-bs-toggle": "tooltip",
            "data-bs-placement": "bottom",
            title: tooltip,
          });
        });

      $('[data-bs-toggle="tooltip"]').tooltip("dispose").tooltip();
    }

    // Initialize the DataTable with columns and configuration
    const letsencrypt_config = {
      tableSelector: "#letsencrypt",
      tableName: "letsencrypt",
      columnVisibilityCondition: (column) => column > 2 && column < 13,
      dataTableOptions: {
        columnDefs: buildColumnDefs(),
        order: [[2, "asc"]], // Sort by domain name
        autoFill: false,
        responsive: true,
        select: {
          style: "multi+shift",
          selector: "td:nth-child(2)",
          headerCheckbox: true,
        },
        layout: layout,
        processing: true,
        serverSide: true,
        ajax: {
          url: `${window.location.pathname}/fetch`,
          type: "POST",
          data: function (d) {
            d.csrf_token = $("#csrf_token").val();
            return d;
          },
          // Add error handling for ajax requests
          error: function (jqXHR, textStatus, errorThrown) {
            console.error("DataTables AJAX error:", textStatus, errorThrown);
            $("#letsencrypt").addClass("d-none");
            $("#letsencrypt-waiting")
              .removeClass("d-none")
              .text(
                "Error loading certificates. Please try refreshing the page."
              )
              .addClass("text-danger");
            // Remove any loading indicators
            $(".dataTables_processing").hide();
          },
        },
        columns: buildColumns(),
        initComplete: function (settings, json) {
          $("#letsencrypt_wrapper .btn-secondary").removeClass("btn-secondary");

          // Hide loading message and show table
          $("#letsencrypt-waiting").addClass("d-none");
          $("#letsencrypt").removeClass("d-none");

          if (isReadOnly) {
            const titleKey = userReadOnly
              ? "tooltip.readonly_user_action_disabled"
              : "tooltip.readonly_db_action_disabled";
            const defaultTitle = userReadOnly
              ? "Your account is readonly, action disabled."
              : "The database is in readonly, action disabled.";
          }
        },
        headerCallback: function (thead) {
          updateHeaderTooltips(thead, headers);
        },
      },
    };

    const dt = initializeDataTable(letsencrypt_config);
    dt.on("draw.dt", function () {
      updateHeaderTooltips(dt.table().header(), headers);
      $(".tooltip").remove();
    });
    dt.on("column-visibility.dt", function (e, settings, column, state) {
      updateHeaderTooltips(dt.table().header(), headers);
      $(".tooltip").remove();
    });

    // Add selection event handler for toggle action button
    dt.on("select.dt deselect.dt", function () {
      const count = dt.rows({ selected: true }).count();
      $(".action-button").toggleClass("disabled", count === 0);
    });
  });
})();
