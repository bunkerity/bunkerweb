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

  let toastNum = 0;
  let actionLock = false;
  const serviceNumber = parseInt($("#services_number").val(), 10) || 0;
  const templates = ($("#templates").val() || "").trim().split(" ");
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const userReadOnly = $("#user-read-only").val().trim() === "True";

  const templatesSearchPanesOptions = [
    {
      label: `<span data-i18n="template.none">${t(
        "template.none",
        "no template",
      )}</span>`,
      value: (rowData) => rowData[5].includes("template.none"),
    },
  ];

  templates.forEach((template) => {
    if (template) {
      templatesSearchPanesOptions.push({
        label: template,
        value: (rowData) => $(rowData[5]).text().trim() === template,
      });
    }
  });

  const setupModal = (services, modal) => {
    const headerList = $(`
      <ul class="list-group list-group-horizontal w-100">
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold">Service name</div>
          </div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="fw-bold">Type</div>
        </li>
      </ul>
    `);
    modal.append(headerList);

    services.forEach((service) => {
      const sanitizedService = service.replace(/\./g, "-");
      const serviceList = $(
        '<ul class="list-group list-group-horizontal w-100"></ul>',
      );

      const listItem = $(`
        <li class="list-group-item" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold">${service}</div>
          </div>
        </li>
      `);
      serviceList.append(listItem);

      const typeClone = $(`#type-${sanitizedService}`)
        .clone()
        .removeClass("highlight");
      const typeListItem = $(`
        <li class="list-group-item" style="flex: 1 0;"></li>
      `);
      typeListItem.append(typeClone);
      serviceList.append(typeListItem);

      modal.append(serviceList);
    });
  };

  const setupConversionModal = (services, conversionType = "draft") => {
    $("#selected-services-input-convert").val(services.join(","));
    setupModal(services, $("#selected-services-convert"));

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
    $("#selected-services-input-delete").val(services.join(","));
    setupModal(services, $("#selected-services-delete"));

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
        columns: [3, 4, 5, 6, 7],
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
    const menu = [10];
    [25, 50, 100].forEach((num) => {
      if (serviceNumber > num) menu.push(num);
    });
    menu.push({ label: t("datatable.length_all", "All"), value: -1 });
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
      extend: "create_service",
    },
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

  $("#modal-delete-services, #modal-convert-services").on(
    "hidden.bs.modal",
    function () {
      $(this)
        .find("#selected-services-convert, #selected-services-delete")
        .empty();
      $(this)
        .find(
          "#selected-services-input-convert, #selected-services-input-delete",
        )
        .val("");
    },
  );

  const getSelectedServices = () =>
    $("tr.selected")
      .map(function () {
        return $(this).find("td:eq(2) a").text().trim();
      })
      .get();

  $.fn.dataTable.ext.buttons.create_service = {
    text: `<span class="tf-icons bx bx-plus"></span><span class="d-none d-md-inline" data-i18n="button.create_service"> ${t(
      "button.create_service",
      "Create new service",
    )}</span>`,
    className: `btn btn-sm rounded me-4 btn-bw-green${
      isReadOnly ? " disabled" : ""
    }`,
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
      window.location.href = `${window.location.href}/new`;
    },
  };

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

      const baseUrl = window.location.href;
      const exportUrl = `${baseUrl}/export?services=${services.join(",")}`;
      window.open(exportUrl, "_blank");
      actionLock = false;
    },
  };

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
    columnVisibilityCondition: (column) => column > 2 && column < 8,
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
          targets: [6, 7],
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
            header: t("searchpane.template", "Template"),
            combiner: "or",
            options: templatesSearchPanesOptions,
          },
          targets: 5,
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
                  new Date() - new Date(rowData[6]) < 86400000,
              },
              {
                label: `<span data-i18n="searchpane.last_7d">${t(
                  "searchpane.last_7d",
                  "Last 7 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[6]) < 604800000,
              },
              {
                label: `<span data-i18n="searchpane.last_30d">${t(
                  "searchpane.last_30d",
                  "Last 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[6]) < 2592000000,
              },
              {
                label: `<span data-i18n="searchpane.older_30d">${t(
                  "searchpane.older_30d",
                  "More than 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[6]) >= 2592000000,
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 6,
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
      ],
      order: [[2, "asc"]],
      autoFill: false,
      responsive: true,
      select: {
        style: "multi+shift",
        selector: "td:nth-child(2)",
        headerCheckbox: true,
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
});
