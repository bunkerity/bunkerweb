$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback, options) => {
          let translated = fallback || key;
          if (options) {
            for (const optKey in options) {
              translated = translated.replace(`{{${optKey}}}`, options[optKey]);
            }
          }
          return translated;
        };

  const BWSelectedList = window.BWSelectedList;
  let toastNum = 0;
  let actionLock = false;
  const serviceNumber = parseInt($("#services_number").val(), 10) || 0;
  const templates = ($("#templates").val() || "").trim().split(" ");
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const userReadOnly = $("#user-read-only").val().trim() === "True";
  const importDragArea = $("#services-drag-area");
  const importFileInput = $("#services-import-file");
  const importFileList = $("#services-import-file-list");

  const templatesSearchPanesOptions = [
    {
      label: `<span data-i18n="template.none">${t(
        "template.none",
        "no template",
      )}</span>`,
      value: (rowData) => rowData[6].includes("template.none"),
    },
  ];

  templates.forEach((template) => {
    if (template) {
      templatesSearchPanesOptions.push({
        label: template,
        value: (rowData) => $(rowData[6]).text().trim() === template,
      });
    }
  });

  // components/selected-list.html "columns" mode -- id_key "name" + hidden_mode
  // "csv" reproduces the old services.join(",") hidden value verbatim.
  const serviceColumns = [
    { key: "name", i18n: "table.header.name", label: "Name", bold: true },
    { key: "type", i18n: "table.header.type", label: "Type", safe: true },
  ];

  // Clone each row's live status badge for the confirm-list "Type" column,
  // stripping any DataTables search-highlight marks first.
  const serviceRows = (services) =>
    services.map((service) => {
      const sanitizedService = service.replace(/\./g, "-");
      const typeClone = $(`#type-${sanitizedService}`)
        .clone()
        .removeClass("highlight");
      return {
        name: service,
        type: typeClone.length ? typeClone[0].outerHTML : "",
      };
    });

  const setupConversionModal = (services, conversionType = "draft") => {
    BWSelectedList.render("#selected-services-convert", serviceRows(services), {
      entity: "services",
      idKey: "name",
      hiddenMode: "csv",
      columns: serviceColumns,
    });

    const convertModal = $("#modal-convert-services");
    convertModal
      .find(".alert")
      .text(
        `Are you sure you want to convert the selected service${
          services.length > 1 ? "s" : ""
        } to ${conversionType}?`,
      );
    convertModal
      .find("button[type=submit]")
      .text(`Convert to ${conversionType}`);
    $("#convertion-type").val(conversionType);

    const modalInstance = new bootstrap.Modal(convertModal);
    modalInstance.show();
  };

  const setupDeletionModal = (services) => {
    BWSelectedList.render("#selected-services-delete", serviceRows(services), {
      entity: "services",
      idKey: "name",
      hiddenMode: "csv",
      columns: serviceColumns,
    });

    const deleteModal = $("#modal-delete-services");
    deleteModal
      .find(".alert")
      .text(
        `Are you sure you want to delete the selected service${
          services.length > 1 ? "s" : ""
        }?`,
      );
    const modalInstance = new bootstrap.Modal(deleteModal);
    modalInstance.show();
  };

  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [3, 4, 5, 6, 7, 8],
      },
    },
    topStart: {},
    topEnd: {
      search: true,
      buttons: [
        {
          extend: "toggle_filters",
          className: "btn btn-sm btn-outline-primary toggle-filters",
        },
      ],
    },
    bottomStart: {
      info: true,
    },
    bottomEnd: {},
  };

  if (serviceNumber > 10) {
    const menu = [10, 25, 50, 100];
    if (serviceNumber > 100) menu.push(500);
    if (serviceNumber > 500) menu.push(1000);
    layout.bottomStart = {
      pageLength: {
        menu: menu,
      },
      info: true,
    };
    layout.bottomEnd.paging = true;
  }

  layout.topStart.buttons = [
    {
      extend: "colvis",
      columns: "th:not(:nth-child(-n+3)):not(:last-child)",
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
            columns: ":visible:not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "csv",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV`,
          bom: true,
          filename: "bw_services",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
          filename: "bw_services",
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
        "Actions",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary action-button disabled",
      buttons: [
        {
          extend: "convert_services",
          text: '<span class="tf-icons bx bx-globe bx-18px me-2"></span>Convert to<span class="d-none d-md-inline"> online</span>',
        },
        {
          extend: "convert_services",
          text: '<span class="tf-icons bx bx-file-blank bx-18px me-2"></span>Convert to<span class="d-none d-md-inline"> draft</span>',
        },
        {
          extend: "export_services",
          text: '<span class="tf-icons bx bx-export bx-18px me-2"></span>Export',
        },
        {
          extend: "delete_services",
          className: "text-danger",
        },
      ],
    },
  ];

  $(document).on("hidden.bs.toast", ".toast", function (event) {
    if (event.target.id.startsWith("feedback-toast")) {
      setTimeout(() => {
        $(this).remove();
      }, 100);
    }
  });

  // #selected-services-{convert,delete,export} rows + hidden input are
  // auto-cleared by static/js/components/selected-list.js's global
  // hidden.bs.modal listener (targets every [data-selected-host]).
  $("#modal-import-services").on("hidden.bs.modal", function () {
    importFileInput.val("");
    importFileList.empty();
    importDragArea.addClass("border-dashed");
    importDragArea.removeClass("bg-primary text-white");
    importDragArea.find("i").addClass("text-primary");
    $("#services-import-configs-options").addClass("d-none");
    $("#services-import-overwrite-configs").prop("checked", false);
  });

  $("#modal-export-services").on("hidden.bs.modal", function () {
    $("#services-export-include-configs").prop("checked", false);
  });

  $("#services-export-confirm").on("click", function () {
    const $modal = $("#modal-export-services");
    const services = BWSelectedList.getIds("#selected-services-export");
    if (services.length === 0) return;
    const includeConfigs = $("#services-export-include-configs").is(":checked");
    window.open(buildExportUrl(services, includeConfigs), "_blank");
    bootstrap.Modal.getInstance($modal[0]).hide();
  });

  const getSelectedServices = () => {
    if (!$.fn.dataTable.isDataTable("#services")) return [];
    return $("#services")
      .DataTable()
      .rows({ selected: true })
      .nodes()
      .to$()
      .map(function () {
        return $(this).find("td:eq(2) a").text().trim();
      })
      .get();
  };

  // "Create service" moved to the page-head band as a real link (#services-create-btn,
  // href="{{ url_for('services.services_service_page', service='new') }}") -- no JS needed.
  // "Import services" moved to the page-head band (#services-import-btn); the action
  // itself is unchanged and reused as-is.
  $("#services-import-btn").on("click", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    importFileInput.val("");
    importFileList.empty();
    const modalInstance = new bootstrap.Modal(
      document.getElementById("modal-import-services"),
    );
    modalInstance.show();
  });

  $.fn.dataTable.ext.buttons.convert_services = {
    action: function (e, dt, node) {
      if (isReadOnly) {
        alert(
          t(
            "alert.readonly_mode",
            "This action is not allowed in read-only mode.",
          ),
        );
        return;
      }
      if (actionLock) return;
      actionLock = true;
      $(".dt-button-background").click();

      const conversionType = $(node).text().trim().split(" ")[2];
      const services = getSelectedServices();
      if (services.length === 0) {
        actionLock = false;
        return;
      }

      const filteredServices = services.filter((service) => {
        const serviceType = $(`#type-${service.replace(/\./g, "-")}`).data(
          "value",
        );
        return serviceType !== conversionType;
      });

      if (filteredServices.length === 0) {
        const feedbackToast = $("#feedback-toast")
          .clone()
          .attr("id", `feedback-toast-${toastNum++}`)
          .removeClass("d-none");
        feedbackToast.find("span").text("Conversion failed");
        feedbackToast
          .find("div.toast-body")
          .text("The selected services are already in the desired state.");
        feedbackToast.appendTo("#feedback-toast-container").toast("show");
        actionLock = false;
        return;
      }

      setupConversionModal(filteredServices, conversionType);
      actionLock = false;
    },
  };

  const servicesWithConfigs = new Set(
    ($("#services_with_configs").val() || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean),
  );

  const buildExportUrl = (services, includeConfigs) => {
    const baseUrl = `${window.location.origin}${window.location.pathname}`;
    const params = new URLSearchParams({ services: services.join(",") });
    if (includeConfigs) params.set("include_configs", "1");
    return `${baseUrl}/export?${params.toString()}`;
  };

  const openExportModal = (services) => {
    if (!services || services.length === 0) return;
    const hasConfigs = services.some((service) =>
      servicesWithConfigs.has(service),
    );
    if (!hasConfigs) {
      // No attached custom configs — skip the modal and download the .env directly.
      window.open(buildExportUrl(services, false), "_blank");
      return;
    }
    BWSelectedList.render(
      "#selected-services-export",
      services.map((service) => ({ id: service, label: service })),
      { entity: "services", idKey: "id", hiddenMode: "csv" },
    );
    $("#services-export-include-configs").prop("checked", false);
    new bootstrap.Modal(
      document.getElementById("modal-export-services"),
    ).show();
  };

  $.fn.dataTable.ext.buttons.export_services = {
    action: function () {
      if (actionLock) return;
      actionLock = true;
      $(".dt-button-background").click();

      const services = getSelectedServices();
      if (services.length === 0) {
        actionLock = false;
        return;
      }

      openExportModal(services);
      actionLock = false;
    },
  };

  $(document).on("click", ".export-service", function () {
    const serviceId = $(this).data("service-id");
    if (!serviceId) return;
    openExportModal([String(serviceId)]);
  });

  $.fn.dataTable.ext.buttons.delete_services = {
    text: '<span class="tf-icons bx bx-trash bx-18px me-2"></span>Delete',
    action: function () {
      if (isReadOnly) {
        alert(
          t(
            "alert.readonly_mode",
            "This action is not allowed in read-only mode.",
          ),
        );
        return;
      }
      if (actionLock) return;
      actionLock = true;
      $(".dt-button-background").click();

      const services = getSelectedServices();
      if (services.length === 0) {
        actionLock = false;
        return;
      }

      setupDeletionModal(services);
      actionLock = false;
    },
  };

  const services_config = {
    tableSelector: "#services",
    tableName: "services",
    columnVisibilityCondition: (column) => column > 2 && column < 9,
    dataTableOptions: {
      columnDefs: [
        {
          orderable: false,
          className: "dtr-control",
          targets: 0,
        },
        {
          orderable: false,
          render: DataTable.render.select(),
          targets: 1,
        },
        { orderable: false, targets: -1 },
        {
          targets: [7, 8],
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
            header: t("searchpane.type", "Type"),
            options: [
              {
                label:
                  '<i class="bx bx-xs bx-globe"></i>&nbsp;<span data-i18n="status.online">Online</span>',
                value: (rowData) => rowData[3].includes("status.online"),
              },
              {
                label:
                  '<i class="bx bx-xs bx-file-blank"></i>&nbsp;<span data-i18n="status.draft">Draft</span>',
                value: (rowData) => rowData[3].includes("status.draft"),
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 3,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.method", "Method"),
            combiner: "or",
            orderable: false,
          },
          targets: 4,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.security_mode", "Security Mode"),
            options: [
              {
                label:
                  '<i class="bx bx-xs bx-shield-alt-2"></i>&nbsp;<span data-i18n="security_mode.block">Block</span>',
                value: (rowData) => rowData[5].includes("security_mode.block"),
              },
              {
                label:
                  '<i class="bx bx-xs bx-show"></i>&nbsp;<span data-i18n="security_mode.detect">Detect</span>',
                value: (rowData) => rowData[5].includes("security_mode.detect"),
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 5,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.template", "Template"),
            combiner: "or",
            options: templatesSearchPanesOptions,
          },
          targets: 6,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.created", "Created"),
            options: [
              {
                label: `<span data-i18n="searchpane.last_24h">${t(
                  "searchpane.last_24h",
                  "Last 24 hours",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[7]) < 86400000,
              },
              {
                label: `<span data-i18n="searchpane.last_7d">${t(
                  "searchpane.last_7d",
                  "Last 7 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[7]) < 604800000,
              },
              {
                label: `<span data-i18n="searchpane.last_30d">${t(
                  "searchpane.last_30d",
                  "Last 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[7]) < 2592000000,
              },
              {
                label: `<span data-i18n="searchpane.older_30d">${t(
                  "searchpane.older_30d",
                  "More than 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[7]) >= 2592000000,
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 7,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.last_update", "Last update"),
            options: [
              {
                label: `<span data-i18n="searchpane.last_24h">${t(
                  "searchpane.last_24h",
                  "Last 24 hours",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[8]) < 86400000,
              },
              {
                label: `<span data-i18n="searchpane.last_7d">${t(
                  "searchpane.last_7d",
                  "Last 7 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[8]) < 604800000,
              },
              {
                label: `<span data-i18n="searchpane.last_30d">${t(
                  "searchpane.last_30d",
                  "Last 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[8]) < 2592000000,
              },
              {
                label: `<span data-i18n="searchpane.older_30d">${t(
                  "searchpane.older_30d",
                  "More than 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[8]) >= 2592000000,
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 8,
        },
      ],
      order: [[2, "asc"]],
      autoFill: false,
      responsive: true,
      select: {
        style: "multi+shift",
        selector: "td:nth-child(2)",
        headerCheckbox: "select-page",
      },
      layout: layout,
      initComplete: function () {
        const $wrapper = $("#services_wrapper");
        $wrapper.find(".btn-secondary").removeClass("btn-secondary");
        if (isReadOnly) {
          $wrapper
            .find(".dt-buttons")
            .attr(
              "data-bs-original-title",
              `${
                userReadOnly
                  ? "Your account is readonly"
                  : "The database is in readonly"
              }, therefore you cannot create new services.`,
            )
            .attr("data-bs-placement", "right")
            .tooltip();
        }
      },
    },
  };

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
    }).then(() => initializeDataTable(services_config));
  } else {
    initializeDataTable(services_config);
  }

  $(document).on("click", ".delete-service", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const service = $(this).data("service-id");
    setupDeletionModal([service]);
  });

  $(document).on("click", ".convert-service", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const service = $(this).data("service-id");
    const conversionType = $(this).data("value");
    setupConversionModal([service], conversionType);
  });

  const validateImportFile = (file) => {
    const fileName = file.name.toLowerCase();
    return (
      fileName.endsWith(".env") ||
      fileName.endsWith(".txt") ||
      fileName.endsWith(".zip")
    );
  };

  const toggleConfigsImportOptions = (file) => {
    const $options = $("#services-import-configs-options");
    if (file && file.name.toLowerCase().endsWith(".zip")) {
      $options.removeClass("d-none");
    } else {
      $options.addClass("d-none");
      $("#services-import-overwrite-configs").prop("checked", false);
    }
  };

  importDragArea.on("click", function () {
    importFileInput.click();
  });

  importDragArea.on("keydown", function (e) {
    if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      importFileInput.click();
    }
  });

  importDragArea.on("dragover", function (e) {
    e.preventDefault();
    importDragArea.removeClass("border-dashed");
    importDragArea.addClass("bg-primary text-white");
    importDragArea.find("i").removeClass("text-primary");
  });

  importDragArea.on("dragleave", function (e) {
    e.preventDefault();
    importDragArea.addClass("border-dashed");
    importDragArea.removeClass("bg-primary text-white");
    importDragArea.find("i").addClass("text-primary");
  });

  importFileInput.on("change", function () {
    const file = this.files && this.files[0];
    importFileList.empty();
    toggleConfigsImportOptions(file);
    if (!file) {
      return;
    }
    if (!validateImportFile(file)) {
      alert("Please upload a valid services export file (.env or .zip).");
      importFileInput.val("");
      toggleConfigsImportOptions(null);
      return;
    }
    const fileSize = (file.size / 1024).toFixed(2);
    importFileList.append(
      `<div class="file-item"><strong>${file.name}</strong> (${fileSize} KB)</div>`,
    );
  });

  importDragArea.on("drop", function (e) {
    e.preventDefault();
    importDragArea.addClass("border-dashed");
    importDragArea.removeClass("bg-primary text-white");
    importDragArea.find("i").addClass("text-primary");
    importFileInput.prop("files", e.originalEvent.dataTransfer.files);
    importFileInput.trigger("change");
  });
});
