$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key; // Fallback

  var actionLock = false;
  let toastNum = 0;
  const configNumber = parseInt($("#configs_number").val());
  const services = ($("#services").val() || "").trim().split(" ");
  const templates = ($("#templates").val() || "").trim().split(" ");
  const configServiceSelection = $("#configs_service_selection").val().trim();
  const configTypeSelection = $("#configs_type_selection")
    .val()
    .trim()
    .toUpperCase();
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const userReadOnly = $("#user-read-only").val().trim() === "True";

  const servicesSearchPanesOptions = [
    {
      label: `<span data-i18n="scope.global">${t(
        "scope.global",
        "global",
      )}</span>`,
      value: (rowData) => rowData[5].includes("scope.global"),
    },
  ];
  const templatesSearchPanesOptions = [
    {
      label: `<span data-i18n="template.none">${t(
        "template.none",
        "no template",
      )}</span>`,
      value: (rowData) => rowData[7].includes("template.none"),
    },
  ];

  services.forEach((service) => {
    if (service) {
      servicesSearchPanesOptions.push({
        label: service,
        value: (rowData) => $(rowData[5]).text().trim() === service,
      });
    }
  });
  templates.forEach((template) => {
    if (template) {
      templatesSearchPanesOptions.push({
        label: template,
        value: (rowData) => $(rowData[7]).text().trim() === template,
      });
    }
  });

  const getConfigId = (config) =>
    `${(config.type || "").toLowerCase()}-${(config.service || "global").replaceAll(".", "_")}-${
      config.name
    }`;

  const buildConfigsList = (configs, $container) => {
    $container.empty();

    const $header = $(`
      <ul class="list-group list-group-horizontal w-100">
        <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold" data-i18n="table.header.name">${t(
              "table.header.name",
              "Name",
            )}</div>
          </div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
          <div class="fw-bold" data-i18n="table.header.type">${t(
            "table.header.type",
            "Type",
          )}</div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
          <div class="fw-bold" data-i18n="table.header.service">${t(
            "table.header.service",
            "Service",
          )}</div>
        </li>
      </ul>`);
    $container.append($header);

    configs.forEach((config) => {
      const list = $(
        `<ul class="list-group list-group-horizontal w-100"></ul>`,
      );
      const listItem = $(`<li class="list-group-item" style="flex: 1 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold">${config.name}</div>
          </div>
        </li>`);
      list.append(listItem);

      const id = getConfigId(config);

      const typeClone = $(`#type-${id}`).clone();
      const typeListItem = $(
        `<li class="list-group-item" style="flex: 1 1 0;"></li>`,
      );
      typeListItem.append(typeClone.removeClass("highlight"));
      list.append(typeListItem);

      const serviceClone = $(`#service-${id}`).clone();
      const serviceListItem = $(
        `<li class="list-group-item" style="flex: 1 1 0;"></li>`,
      );
      serviceListItem.append(serviceClone.removeClass("highlight"));
      list.append(serviceListItem);
      serviceClone
        .find('[data-bs-toggle="tooltip"]')
        .tooltip("dispose")
        .tooltip();

      $container.append(list);
    });
  };

  const setupConversionModal = (configs, conversionType = "draft") => {
    const convertModal = $("#modal-convert-configs");
    buildConfigsList(configs, $("#selected-configs-convert"));

    const alertText = t(
      "modal.body.confirm_configs_conversion_to",
      `Are you sure you want to convert the selected config${
        configs.length > 1 ? "s" : ""
      } to ${conversionType}?`,
      { state: conversionType },
    );
    convertModal.find(".alert").text(alertText);
    const buttonLabel = t(
      "button.convert_configs_to",
      `Convert to ${conversionType}`,
      { state: conversionType },
    );
    convertModal.find("button[type=submit]").text(buttonLabel);
    $("#conversion-type").val(conversionType);

    const configsToSubmit = configs.map((cfg) => ({
      ...cfg,
      type: (cfg.type || "").toLowerCase(),
      service: cfg.service === t("scope.global", "global") ? null : cfg.service,
    }));
    $("#selected-configs-input-convert").val(JSON.stringify(configsToSubmit));

    const modalInstance = new bootstrap.Modal(convertModal[0]);
    modalInstance.show();
  };

  const setupDeletionModal = (configs) => {
    const delete_modal = $("#modal-delete-configs");
    buildConfigsList(configs, $("#selected-configs-delete"));

    const modalInstance = new bootstrap.Modal(delete_modal[0]);

    const alertTextKey =
      configs.length > 1
        ? "modal.body.delete_confirmation_alert_plural"
        : "modal.body.delete_confirmation_alert";
    delete_modal
      .find(".alert")
      .text(
        t(
          alertTextKey,
          `Are you sure you want to delete the selected custom configuration${
            configs.length > 1 ? "s" : ""
          }?`,
        ),
      );
    modalInstance.show();

    const configsToSubmit = configs.map((cfg) => ({
      ...cfg,
      type: (cfg.type || "").toLowerCase(),
      service: cfg.service === t("scope.global", "global") ? null : cfg.service,
    }));
    $("#selected-configs-input-delete").val(JSON.stringify(configsToSubmit));
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

  if (configNumber > 10) {
    const menu = [10];
    if (configNumber > 25) menu.push(25);
    if (configNumber > 50) menu.push(50);
    if (configNumber > 100) menu.push(100);
    menu.push({ label: t("datatable.length_all", "All"), value: -1 });
    layout.bottomStart = {
      pageLength: { menu: menu },
      info: true,
    };
    layout.bottomEnd.paging = true;
  }

  layout.topStart.buttons = [
    {
      extend: "create_config",
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
          console.warn(
            `ColVis: No data-i18n key found for column index ${idx}, using header text or title: '${translatedTitle}'`,
          );
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
          filename: "bw_custom_configs",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
          filename: "bw_custom_configs",
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
          extend: "convert_configs",
          text: '<span class="tf-icons bx bx-globe bx-18px me-2"></span>Convert to<span class="d-none d-md-inline"> online</span>',
          attr: { "data-convert-to": "online" },
        },
        {
          extend: "convert_configs",
          text: '<span class="tf-icons bx bx-file-blank bx-18px me-2"></span>Convert to<span class="d-none d-md-inline"> draft</span>',
          attr: { "data-convert-to": "draft" },
        },
        {
          extend: "delete_configs",
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

  $("#modal-delete-configs, #modal-convert-configs").on(
    "hidden.bs.modal",
    function () {
      $("#selected-configs-delete, #selected-configs-convert").empty();
      $("#selected-configs-input-delete, #selected-configs-input-convert").val(
        "",
      );
      $("#conversion-type").val("draft");
    },
  );

  const getSelectedConfigs = () => {
    const configs = [];
    $("tr.selected").each(function () {
      const $row = $(this);
      const name = $row.find("td:eq(2)").find("a").text().trim();
      const type = $row.find("td:eq(3)").text().trim();
      let service;
      const $serviceCell = $row.find("td:eq(5)");
      const $serviceLink = $serviceCell.find("a");
      if ($serviceLink.length > 0) {
        service = $serviceLink.text().trim();
      } else {
        const $serviceSpan = $serviceCell.find("span[data-i18n]");
        service = $serviceSpan.length
          ? $serviceSpan.text().trim()
          : $serviceCell.text().trim();
      }

      const normalizedService =
        service === t("scope.global", "global") ? "global" : service;

      configs.push({ name: name, type: type, service: normalizedService });
    });
    return configs;
  };

  $.fn.dataTable.ext.buttons.create_config = {
    text: `<span class="tf-icons bx bx-plus"></span><span class="d-none d-md-inline" data-i18n="button.create_config"> ${t(
      "button.create_config",
      "Create new custom config",
    )}</span>`,
    className: `btn btn-sm rounded me-4 btn-bw-green${
      isReadOnly ? " disabled" : ""
    }`,
    action: function (e, dt, node, config) {
      if (isReadOnly) {
        alert(
          t(
            "alert.readonly_mode",
            "This action is not allowed in read-only mode.",
          ),
        );
        return;
      }
      window.location.href = `${window.location.pathname}/new`;
    },
  };

  $.fn.dataTable.ext.buttons.convert_configs = {
    action: function (e, dt, node, config) {
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

      const conversionType =
        $(node).data("convert-to") ||
        $(node).text().trim().split(" ").pop().toLowerCase();
      const configs = getSelectedConfigs();
      if (configs.length === 0) {
        actionLock = false;
        return;
      }

      const filteredConfigs = configs.filter((cfg) => {
        const statusValue = $(`#status-${getConfigId(cfg)}`).data("value");
        return statusValue !== conversionType;
      });

      if (filteredConfigs.length === 0) {
        const feedbackToast = $("#feedback-toast")
          .clone()
          .attr("id", `feedback-toast-${toastNum++}`)
          .removeClass("d-none");
        feedbackToast.find("span").text("Conversion failed");
        feedbackToast
          .find("div.toast-body")
          .text("The selected configs are already in the desired state.");
        feedbackToast.appendTo("#feedback-toast-container").toast("show");
        actionLock = false;
        return;
      }

      setupConversionModal(filteredConfigs, conversionType);
      actionLock = false;
    },
  };

  $.fn.dataTable.ext.buttons.delete_configs = {
    text: `<span class="tf-icons bx bx-trash bx-18px me-2"></span><span data-i18n="button.delete">${t(
      "button.delete",
      "Delete",
    )}</span>`,
    action: function (e, dt, node, config) {
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
      $(".dt-button-background").click(); // Close collection dropdown if open

      const configs = getSelectedConfigs();
      if (configs.length === 0) {
        actionLock = false;
        return;
      }
      setupDeletionModal(configs);
      actionLock = false;
    },
  };

  const configs_config = {
    tableSelector: "#configs",
    tableName: "configs",
    columnVisibilityCondition: (column) => column > 2 && column < 9,
    dataTableOptions: {
      columnDefs: [
        { orderable: false, className: "dtr-control", targets: 0 },
        { orderable: false, render: DataTable.render.select(), targets: 1 },
        { orderable: false, targets: -1 },
        { visible: false, targets: 8 },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.type", "Type"),
            options: [
              {
                label: '<i class="bx bx-xs bx-window-alt"></i>HTTP',
                value: function (rowData, rowIdx) {
                  return $(rowData[3]).text().trim() === "HTTP";
                },
              },
              {
                label: '<i class="bx bx-xs bx-window-alt"></i>SERVER_HTTP',
                value: function (rowData, rowIdx) {
                  return $(rowData[3]).text().trim() === "SERVER_HTTP";
                },
              },
              {
                label:
                  '<i class="bx bx-xs bx-window-alt"></i>DEFAULT_SERVER_HTTP',
                value: function (rowData, rowIdx) {
                  return $(rowData[3]).text().trim() === "DEFAULT_SERVER_HTTP";
                },
              },
              {
                label: '<i class="bx bx-xs bx-shield-quarter"></i>MODSEC_CRS',
                value: function (rowData, rowIdx) {
                  return $(rowData[3]).text().trim() === "MODSEC_CRS";
                },
              },
              {
                label: '<i class="bx bx-xs bx-shield-alt-2"></i>MODSEC',
                value: function (rowData, rowIdx) {
                  return $(rowData[3]).text().trim() === "MODSEC";
                },
              },
              {
                label: '<i class="bx bx-xs bx-network-chart"></i>STREAM',
                value: function (rowData, rowIdx) {
                  return $(rowData[3]).text().trim() === "STREAM";
                },
              },
              {
                label: '<i class="bx bx-xs bx-network-chart"></i>SERVER_STREAM',
                value: function (rowData, rowIdx) {
                  return $(rowData[3]).text().trim() === "SERVER_STREAM";
                },
              },
              {
                label:
                  '<i class="bx bx-xs bx-shield-alt"></i>CRS_PLUGINS_BEFORE',
                value: function (rowData, rowIdx) {
                  return $(rowData[3]).text().trim() === "CRS_PLUGINS_BEFORE";
                },
              },
              {
                label:
                  '<i class="bx bx-xs bx-shield-alt"></i>CRS_PLUGINS_AFTER',
                value: function (rowData, rowIdx) {
                  return $(rowData[3]).text().trim() === "CRS_PLUGINS_AFTER";
                },
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
            header: t("searchpane.active", "Active"),
            combiner: "or",
            orderable: false,
          },
          targets: 4,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.service", "Service"),
            combiner: "or",
            options: servicesSearchPanesOptions,
          },
          targets: 5,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.status", "Status"),
            combiner: "or",
            options: [
              {
                label: `<span data-i18n="status.online">${t("status.online", "Online")}</span>`,
                value: function (rowData) {
                  return (
                    $(rowData[6]).find("[data-value]").data("value") ===
                    "online"
                  );
                },
              },
              {
                label: `<span data-i18n="status.draft">${t("status.draft", "Draft")}</span>`,
                value: function (rowData) {
                  return (
                    $(rowData[6]).find("[data-value]").data("value") === "draft"
                  );
                },
              },
            ],
          },
          targets: 6,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.template", "Template"),
            combiner: "or",
            options: templatesSearchPanesOptions,
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
      initComplete: function (settings, json) {
        $("#configs_wrapper .btn-secondary").removeClass("btn-secondary");
        if (isReadOnly) {
          const titleKey = userReadOnly
            ? "tooltip.readonly_user_action_disabled"
            : "tooltip.readonly_db_action_disabled";
          const defaultTitle = userReadOnly
            ? "Your account is readonly, action disabled."
            : "The database is in readonly, action disabled.";
          $("#configs_wrapper .dt-buttons")
            .attr(
              "data-bs-original-title",
              t(titleKey, defaultTitle, { action: t("button.create_config") }),
            )
            .attr("data-bs-placement", "right")
            .tooltip();
        }
      },
    },
  };

  // Trigger initial search pane selections if applicable
  if (configTypeSelection) {
    const typeLabelElement = $(
      `#DataTables_Table_0 span[data-i18n='${configTypeMap[configTypeSelection]?.key}']`,
    );
    if (typeLabelElement.length) {
      typeLabelElement.closest("span.dtsp-name").trigger("click"); // Click the parent span which has the DT handler
    } else {
      console.warn(
        `Could not find search pane option for type: ${configTypeSelection}`,
      );
    }
  }

  if (configServiceSelection) {
    const serviceLabelElement = $(
      `#DataTables_Table_2 span:contains('${configServiceSelection}')`,
    );
    if (serviceLabelElement.length) {
      const targetElement = serviceLabelElement.filter(
        (_, el) => $(el).text().trim() === configServiceSelection,
      );
      if (targetElement.length) {
        targetElement.closest("span.dtsp-name").trigger("click");
      } else {
        console.warn(
          `Could not find exact match for service pane option: ${configServiceSelection}`,
        );
      }
    } else {
      console.warn(
        `Could not find any search pane option containing: ${configServiceSelection}`,
      );
    }
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
      const dt = initializeDataTable(configs_config);
      // Show/hide filters based on initial selections
      if (configTypeSelection || configServiceSelection) {
        dt.searchPanes.container().show();
        if (typeof dt.updateFilterToggleUI === "function") {
          dt.updateFilterToggleUI(true);
        } else if (dt.filterToggleSelectors) {
          const selectors = dt.filterToggleSelectors;
          if (selectors.show) $(selectors.show).addClass("d-none");
          if (selectors.hide) $(selectors.hide).removeClass("d-none");
        }
      }
      return dt;
    });
  }

  // Handle individual delete button click
  $(document).on("click", ".delete-config", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const service = $(this).data("config-service");
    const config = {
      name: $(this).data("config-name"),
      type: $(this).data("config-type"),
      service: service === "global" ? null : service,
    };
    setupDeletionModal([config]);
  });

  $(document).on("click", ".convert-config", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const service = $(this).data("config-service");
    const config = {
      name: $(this).data("config-name"),
      type: $(this).data("config-type"),
      service: service || "global",
    };
    const conversionType = $(this).data("value");
    setupConversionModal([config], conversionType);
  });
});
