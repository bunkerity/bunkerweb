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

    // Set up the delete confirmation modal
    const setupDeleteCertModal = (certs) => {
      const $modalBody = $("#deleteCertContent");
      $modalBody.empty(); // Clear previous content

      if (certs.length === 1) {
        $modalBody.html(
          `<p>You are about to delete the certificate for: <strong>${certs[0].domain}</strong></p>`
        );
        $("#confirmDeleteCertBtn").data("cert-name", certs[0].domain);
      } else {
        const certList = certs
          .map((cert) => `<li>${cert.domain}</li>`)
          .join("");
        $modalBody.html(
          `<p>You are about to delete these certificates:</p>
         <ul>${certList}</ul>`
        );
        $("#confirmDeleteCertBtn").data(
          "cert-names",
          certs.map((c) => c.domain)
        );
      }
    };

    // Set up error modal
    const showErrorModal = (title, message) => {
      $("#errorModalLabel").text(title);
      $("#errorModalContent").html(message);
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

    // Create columns configuration
    function buildColumnDefs() {
      return [
        { orderable: false, className: "dtr-control", targets: 0 },
        { orderable: false, render: DataTable.render.select(), targets: 1 },
        { type: "string", targets: 2 }, // domain
        { orderable: true, targets: -1 },
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
