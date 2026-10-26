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
  const configsData = JSON.parse($("#configs-data").val());
  const rowConfig = (node) => configsData[Number(node.dataset.configIndex)];

  const importDragArea = $("#configs-drag-area");
  const importFileInput = $("#configs-import-file");
  const importFileList = $("#configs-import-file-list");

  const servicesSearchPanesOptions = [
    {
      label: `<span data-i18n="scope.global">${t(
        "scope.global",
        "global",
      )}</span>`,
      value: (rowData) => rowData[5].includes('data-value="global"'),
    },
  ];
  const templatesSearchPanesOptions = [
    {
      label: `<span data-i18n="template.none">${t(
        "template.none",
        "no template",
      )}</span>`,
      value: (rowData) => rowData[7].includes('data-value="none"'),
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

  const getStatusValue = (cellData) => {
    if (!cellData) return "";
    const $wrapper = $("<div>").html(cellData);
    const value = $wrapper.find("[data-value]").data("value");
    if (value) return value;
    const text = $wrapper.text().trim();
    if (!text) return "";
    const normalized = text.toLowerCase();
    if (normalized === t("status.online", "Online").toLowerCase())
      return "online";
    if (normalized === t("status.draft", "Draft").toLowerCase()) return "draft";
    return normalized;
  };

  // Confirmation lists use text-only values from the live table. The shared
  // selected-list component deliberately never inserts row HTML.
  const configsListColumns = [
    {
      key: "name",
      i18n: "table.header.name",
      label: t("table.header.name", "Name"),
      bold: true,
    },
    {
      key: "type",
      i18n: "table.header.type",
      label: t("table.header.type", "Type"),
    },
    {
      key: "service",
      i18n: "table.header.service",
      label: t("table.header.service", "Service"),
    },
  ];

  const buildConfigsRows = (configs) =>
    configs.map((config) => {
      return {
        name: config.name,
        type: config.type.toUpperCase(),
        service:
          config.service === "global"
            ? t("scope.global", "Global")
            : config.service,
      };
    });

  const renderSelectedConfigs = (hostSelector, configs) =>
    BWSelectedList.render(hostSelector, buildConfigsRows(configs), {
      entity: "configs",
      hiddenMode: "none",
      columns: configsListColumns,
    });

  const setupConversionModal = (configs, conversionType = "draft") => {
    const convertModal = $("#modal-convert-configs");
    renderSelectedConfigs("#selected-configs-convert", configs);

    const alertText = t(
      `modal.body.confirm_${
        configs.length > 1 ? "configs" : "config"
      }_conversion_${conversionType}`,
      `Are you sure you want to convert the selected config${
        configs.length > 1 ? "s" : ""
      } to ${conversionType}?`,
    );
    convertModal.find(".alert").text(alertText);
    const buttonLabel = t(
      `button.convert_to_${conversionType}`,
      `Convert to ${conversionType}`,
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
    renderSelectedConfigs("#selected-configs-delete", configs);

    const modalInstance = new bootstrap.Modal(delete_modal[0]);

    // Not the shared `delete_confirmation_alert(_plural)` (M25): that key says "instance",
    // wrong here. `confirm_configs_deletion_alert(_plural)` already exists and says the right
    // thing -- it just was not the key this modal asked for.
    const alertTextKey =
      configs.length > 1
        ? "modal.body.confirm_configs_deletion_alert_plural"
        : "modal.body.confirm_configs_deletion_alert";
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
        columns: [4, 5, 6, 7],
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
    const menu = [10, 25, 50, 100];
    if (configNumber > 100) menu.push(500);
    if (configNumber > 500) menu.push(1000);
    layout.bottomStart = {
      pageLength: { menu: menu },
      info: true,
    };
    layout.bottomEnd.paging = true;
  }

  layout.topStart.buttons = [
    // "Create custom config" moved to the page-head band (configs.html); import stays here.
    {
      extend: "import_configs",
    },
    {
      extend: "colvis",
      columns: "th:not(:nth-child(-n+3)):not(:last-child)",
      text: `<span class="tf-icons bx bx-columns bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.columns">${t(
        "button.columns",
        "Columns",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary rounded-start",
      // L2: the header is already server-translated (native i18n Lot D dropped the client-side
      // `data-i18n` attribute this used to look for), so every column landed in the "not found"
      // branch and logged a console warning on load. The header text is the translation.
      columnText: function (dt, idx, title) {
        const headerCell = dt.column(idx).header();
        const translatedTitle = $(headerCell).text().trim() || title;
        return `${idx + 1}. <span>${translatedTitle}</span>`;
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
            orthogonal: "export",
            columns: ":visible:not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "csv",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV`,
          bom: true,
          filename: "bw_custom_configs",
          exportOptions: {
            orthogonal: "export",
            modifier: { search: "none" },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
          filename: "bw_custom_configs",
          exportOptions: {
            orthogonal: "export",
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
          text: `<span class="tf-icons bx bx-globe bx-18px me-2"></span><span data-i18n="button.convert_to_online">${t(
            "button.convert_to_online",
            "Convert to online",
          )}</span>`,
          attr: { "data-convert-to": "online" },
        },
        {
          extend: "convert_configs",
          text: `<span class="tf-icons bx bx-file-blank bx-18px me-2"></span><span data-i18n="button.convert_to_draft">${t(
            "button.convert_to_draft",
            "Convert to draft",
          )}</span>`,
          attr: { "data-convert-to": "draft" },
        },
        {
          extend: "export_configs",
          text: `<span class="tf-icons bx bx-export bx-18px me-2"></span><span data-i18n="button.export">${t(
            "button.export",
            "Export",
          )}</span>`,
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

  // The visible recap list (#selected-configs-delete/-convert) is a
  // components/selected-list.html host -- static/js/components/selected-list.js
  // clears it back to its empty state on "hidden.bs.modal" itself, so this
  // handler only needs to reset the fields that macro doesn't own.
  $("#modal-delete-configs, #modal-convert-configs").on(
    "hidden.bs.modal",
    function () {
      $("#selected-configs-input-delete, #selected-configs-input-convert").val(
        "",
      );
      $("#conversion-type").val("draft");
    },
  );

  $("#modal-import-configs").on("hidden.bs.modal", function () {
    importFileInput.val("");
    importFileList.empty();
    $("#configs-import-overwrite").prop("checked", false);
    importDragArea.addClass("border-dashed");
    importDragArea.removeClass("bg-primary text-white");
    importDragArea.find("i").addClass("text-primary");
  });

  const getSelectedConfigs = () => {
    const configs = [];
    if (!$.fn.dataTable.isDataTable("#configs")) return configs;
    $("#configs")
      .DataTable()
      .rows({ selected: true })
      .nodes()
      .to$()
      .each(function () {
        const config = rowConfig(this);
        configs.push({
          name: config.name,
          type: config.type.toUpperCase(),
          service: config.service,
        });
      });
    return configs;
  };

  $.fn.dataTable.ext.buttons.import_configs = {
    text: `<span class="tf-icons bx bx-import bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.import_configs">${t(
      "button.import_configs",
      "Import custom configurations",
    )}</span>`,
    className: `btn btn-sm rounded btn-outline-bw-green me-2${
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
      importFileInput.val("");
      importFileList.empty();
      $("#configs-import-overwrite").prop("checked", false);
      const modalInstance = new bootstrap.Modal(
        document.getElementById("modal-import-configs"),
      );
      modalInstance.show();
    },
  };

  $.fn.dataTable.ext.buttons.export_configs = {
    action: function () {
      if (actionLock) return;
      actionLock = true;
      $(".dt-button-background").click();

      const configs = getSelectedConfigs();
      if (configs.length === 0) {
        actionLock = false;
        return;
      }

      const baseUrl = `${window.location.origin}${window.location.pathname}`;
      const payload = encodeURIComponent(JSON.stringify(configs));
      window.open(`${baseUrl}/export?configs=${payload}`, "_blank");
      actionLock = false;
    },
  };

  $.fn.dataTable.ext.buttons.create_config = {
    text: `<span class="tf-icons bx bx-plus"></span><span class="d-none d-md-inline" data-i18n="button.create_config"> ${t(
      "button.create_config",
      "Create new custom config",
    )}</span>`,
    className: `btn btn-sm rounded me-2 btn-bw-green${
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
        const config = configsData.find(
          (item) => getConfigId(item) === getConfigId(cfg),
        );
        const statusValue = config?.is_draft ? "draft" : "online";
        return statusValue !== conversionType;
      });

      if (filteredConfigs.length === 0) {
        const feedbackToast = $("#feedback-toast")
          .clone()
          .attr("id", `feedback-toast-${toastNum++}`)
          .removeClass("d-none");
        feedbackToast
          .find("span")
          .text(t("toast.header.conversion_failed", "Conversion failed"));
        feedbackToast
          .find("div.toast-body")
          .text(
            t(
              "toast.body.selected_items_already_in_state",
              "The selected items are already in the requested state.",
            ),
          );
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
        // The cell also shows the scope; sorting, filtering and exports keep using the bare name.
        {
          render: (data, type, row, meta) =>
            type === "display" ? data : configsData[meta.row].name,
          targets: 2,
        },
        { visible: false, targets: [4, 5, 6, 7, 8] },
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
                  '<i class="bx bx-xs bx-network-chart"></i>DEFAULT_SERVER_STREAM',
                value: function (rowData, rowIdx) {
                  return (
                    $(rowData[3]).text().trim() === "DEFAULT_SERVER_STREAM"
                  );
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
                  return getStatusValue(rowData[6]) === "online";
                },
              },
              {
                label: `<span data-i18n="status.draft">${t("status.draft", "Draft")}</span>`,
                value: function (rowData) {
                  return getStatusValue(rowData[6]) === "draft";
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
        headerCheckbox: "select-page",
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

  const applyInitialFilters = (dt) => {
    const container = dt.searchPanes?.container?.();
    if (!container) return;

    const $container = $(container);
    const clickPaneOption = (selector, description) => {
      const $match = $container.find(selector).first();
      if ($match.length) {
        const $target = $match.closest("span.dtsp-name");
        ($target.length ? $target : $match).trigger("click");
        return true;
      }
      console.warn(`Could not find search pane option for ${description}`);
      return false;
    };

    // The type tabs own the type filter (setFilters); the Type search pane is not shown.
    if (configServiceSelection) {
      const isGlobal = configServiceSelection.toLowerCase() === "global";
      if (isGlobal) {
        clickPaneOption(
          "span.dtsp-name [data-i18n='scope.global']",
          `service: ${configServiceSelection}`,
        );
      } else {
        const serviceSelector = "span.dtsp-name";
        const $serviceMatch = $container
          .find(serviceSelector)
          .filter((_, el) => $(el).text().trim() === configServiceSelection)
          .first();
        if ($serviceMatch.length) {
          $serviceMatch.trigger("click");
        } else {
          console.warn(
            `Could not find search pane option for service: ${configServiceSelection}`,
          );
        }
      }
    }
  };

  const dt = initializeDataTable(configs_config);
  // Keep the shared toolbar/filter/selection engine; its table becomes the file list.
  const scroll = $(dt.table().container()).find(".bw-table-scroll");
  scroll.wrap(
    '<div class="row g-3 align-items-start"><div id="configs-files" class="col-lg-4"></div></div>',
  );
  const split = $("#configs-files").parent();
  const preview = $("#configs-preview").removeClass("d-none").appendTo(split);
  const editor = ace.edit("configs-preview-editor");
  editor.setOptions({
    readOnly: true,
    showPrintMargin: false,
    fontSize: "14px",
    wrap: true,
    tabSize: 2,
  });
  const setPreviewTheme = () =>
    editor.setTheme(
      `ace/theme/cloud9_${$("#theme").val() === "dark" ? "night" : "day"}`,
    );
  setPreviewTheme();
  $("#dark-mode-toggle").on("change", () => setTimeout(setPreviewTheme, 30));
  let currentConfig = null;
  let currentType = "";
  let currentScope = "all";
  // Imported and env-origin names may already carry the suffix.
  const fileName = (config) =>
    config.name.endsWith(".conf") ? config.name : `${config.name}.conf`;
  const normalizeType = (type) => type.replaceAll("-", "_").toUpperCase();
  const showConfig = (config) => {
    currentConfig = config;
    $("#configs-preview-empty").toggleClass("d-none", !!config);
    $("#configs-preview-editor").toggleClass("d-none", !config);
    $(
      "#configs-preview-full, #configs-preview-lint, #configs-preview-download",
    ).prop("disabled", !config);
    $("#configs-preview-edit").toggleClass("d-none", !config);
    $("#configs-preview-name").text(
      config ? fileName(config) : t("configs.console.files"),
    );
    $("#configs-preview-lint-result").empty();
    $("#configs-preview-meta").empty();
    $(dt.rows().nodes()).removeClass("table-active");
    if (!config) {
      editor.setValue("", -1);
      return;
    }
    const node = dt
      .rows()
      .nodes()
      .toArray()
      .find((node) => rowConfig(node) === config);
    $(node).addClass("table-active");
    // Clone metadata only; no executable file content enters HTML.
    const row = dt.row(node);
    for (const index of [3, 4, 5, 6, 7]) {
      const chip = document.createElement("span");
      chip.innerHTML = row.data()[index];
      // The row's own cells keep the ids; a copy would duplicate them.
      $(chip).find("[id]").removeAttr("id");
      $("#configs-preview-meta").append(chip);
    }
    $("#configs-preview-icon").attr(
      "class",
      `bx bx-${config.service === "global" ? "globe" : "server"}`,
    );
    $("#configs-preview-edit")
      .attr(
        "href",
        `${window.location.pathname}/${[config.service, config.type, config.name].map(encodeURIComponent).join("/")}`,
      )
      .text(
        t(
          !isReadOnly &&
            (config.template || ["ui", "api", "wizard"].includes(config.method))
            ? "configs.console.edit"
            : "configs.console.view",
        ),
      );
    editor.session.setMode(
      /^(MODSEC|CRS)/i.test(config.type) ? "ace/mode/text" : "ace/mode/nginx",
    );
    editor.setValue(config.data || "", -1);
    editor.session.clearAnnotations();
    editor.resize();
  };
  const syncPreview = () => {
    const visible = dt
      .rows({ search: "applied" })
      .nodes()
      .toArray()
      .map(rowConfig);
    showConfig(
      visible.includes(currentConfig) ? currentConfig : visible[0] || null,
    );
  };
  $(document).on("click", "a.config-preview", function (event) {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)
      return;
    event.preventDefault();
    showConfig(rowConfig($(this).closest("tr")[0]));
  });
  $("#configs-preview-lint").on("click", () => {
    if (!currentConfig) return;
    const annotations = window.BWConfigLint(
      editor.getValue(),
      currentConfig.type,
    );
    editor.session.setAnnotations(annotations);
    $("#configs-preview-lint-result").text(
      t(
        /^(MODSEC|CRS)/i.test(currentConfig.type)
          ? "configs.console.lint_skipped"
          : annotations.length
            ? "configs.console.lint_warnings"
            : "configs.console.lint_clean",
        { count: annotations.length },
      ),
    );
  });
  $("#configs-preview-download").on("click", () => {
    if (!currentConfig) return;
    const url = URL.createObjectURL(
      new Blob([currentConfig.data || ""], {
        type: "text/plain;charset=utf-8",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName(currentConfig);
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  $("#configs-preview-full").on("click", function () {
    const expanded = this.getAttribute("aria-pressed") !== "true";
    $(this)
      .attr("aria-pressed", String(expanded))
      .text(
        t(
          expanded
            ? "configs.console.restore_view"
            : "configs.console.full_view",
        ),
      );
    $("#configs-files").toggleClass("d-none", expanded);
    preview.toggleClass("col-lg-8", !expanded).toggleClass("col-12", expanded);
    editor.resize();
  });
  const knownTypes = $(".config-type-tab")
    .map((_, el) => el.dataset.type)
    .get();
  const setFilters = ({ type = currentType, scope = currentScope } = {}) => {
    currentType = type;
    currentScope = scope;
    $(".config-type-tab").each(function () {
      const active = this.dataset.type === type;
      $(this)
        .toggleClass("btn-primary", active)
        .toggleClass("btn-outline-secondary", !active)
        .attr("aria-pressed", String(active));
    });
    $(".config-scope-tab").each(function () {
      const active = this.dataset.scope === scope;
      $(this)
        .toggleClass("btn-primary", active)
        .toggleClass("btn-outline-secondary", !active)
        .attr("aria-pressed", String(active));
    });
    $("#configs-type-select").val(type);
    dt.draw();
    dt.rows({ search: "removed" }).deselect();
  };
  // Scope and type match the inventory ids, never the translated labels.
  $.fn.dataTable.ext.search.push((settings, data, index) => {
    if (settings.nTable.id !== "configs") return true;
    const config = rowConfig(dt.row(index).node());
    if (currentType && normalizeType(config.type) !== currentType) return false;
    return (
      currentScope === "all" ||
      (currentScope === "global") === (config.service === "global")
    );
  });
  $(".config-type-tab").on("click", function () {
    setFilters({ type: this.dataset.type });
  });
  $("#configs-type-select").on("change", function () {
    setFilters({ type: this.value });
  });
  $(".config-scope-tab").on("click", function () {
    setFilters({ scope: this.dataset.scope });
  });
  $(".config-type-tab").each(function () {
    $(this)
      .find(".config-type-count")
      .text(
        configsData.filter(
          (config) => normalizeType(config.type) === this.dataset.type,
        ).length,
      );
  });
  // The list sits in a clipping scroll box: fixed positioning lets the row menu escape it.
  const fixMenus = () =>
    $(".bw-table-scroll .dropdown-toggle").each(function () {
      bootstrap.Dropdown.getOrCreateInstance(this, {
        popperConfig: { strategy: "fixed" },
      });
    });
  dt.on("draw.dt", fixMenus);
  dt.on("draw.dt", syncPreview);
  applyInitialFilters(dt);
  const initialType = normalizeType(configTypeSelection);
  setFilters({
    type: knownTypes.includes(initialType) ? initialType : knownTypes[0],
  });
  fixMenus();
  dt.columns.adjust();
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
    const service = $(this).attr("data-config-service");
    const config = {
      name: $(this).attr("data-config-name"),
      type: $(this).attr("data-config-type"),
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
    const service = $(this).attr("data-config-service");
    const config = {
      name: $(this).attr("data-config-name"),
      type: $(this).attr("data-config-type"),
      service: service || "global",
    };
    const conversionType = $(this).data("value");
    setupConversionModal([config], conversionType);
  });

  const validateImportFile = (file) => {
    if (!file) return false;
    const name = (file.name || "").toLowerCase();
    if (name.endsWith(".json")) return true;
    return (file.type || "").toLowerCase().includes("json");
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
    const file = this.files[0];
    importFileList.empty();
    if (!file) return;
    if (!validateImportFile(file)) {
      alert(
        t(
          "alert.configs_import_invalid_file",
          "Please upload a valid custom configurations export file (.json).",
        ),
      );
      importFileInput.val("");
      return;
    }
    importFileList.append(
      `<div class="alert alert-info text-center" role="alert">${file.name}</div>`,
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
