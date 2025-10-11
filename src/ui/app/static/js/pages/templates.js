$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback, options) => {
          // Basic fallback supporting simple interpolation
          let translated = fallback || key;
          if (options) {
            for (const optKey in options) {
              translated = translated.replace(`{{${optKey}}}`, options[optKey]);
            }
          }
          return translated;
        };

  var toastNum = 0;
  var actionLock = false;
  var showLoadingModal = false;
  const templateNumber = parseInt($("#templates_number").val());
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const userReadOnly = $("#user-read-only").val().trim() === "True";

  const setupDeletionModal = (templates) => {
    const delete_modal = $("#modal-delete-templates");
    const $modalBody = $("#selected-templates");
    $modalBody.empty(); // Clear previous content

    $("#selected-templates-input").val(templates.join(","));

    const $header = $(`
      <ul class="list-group list-group-horizontal w-100">
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold" data-i18n="table.header.id">${t(
              "table.header.id",
              "ID",
            )}</div>
          </div>
        </li>
      </ul>`);
    $modalBody.append($header);

    templates.forEach((templateId) => {
      const $row = $(
        `<ul class="list-group list-group-horizontal w-100"></ul>`,
      );

      // ID item
      const $idItem = $(`<li class="list-group-item" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold">${templateId}</div>
          </div>
        </li>`);
      $row.append($idItem);

      $modalBody.append($row);
    });

    // Use plural/singular i18n key for alert
    const alertTextKey =
      templates.length > 1
        ? "modal.body.delete_confirmation_alert_plural"
        : "modal.body.delete_confirmation_alert";
    const defaultAlertText = `Are you sure you want to delete the selected template${
      templates.length > 1 ? "s" : ""
    }?`;
    delete_modal.find(".alert").text(t(alertTextKey, defaultAlertText));

    const modalTemplate = new bootstrap.Modal(delete_modal[0]);
    modalTemplate.show();
  };

  const execForm = (templates, action) => {
    // Create a form element using jQuery and set its attributes
    const form = $("<form>", {
      method: "POST",
      action: `${window.location.pathname}/${action}`, // Action like 'reload', 'stop'
      class: "visually-hidden",
    });

    // Add CSRF token and templates as hidden inputs
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
        name: "templates",
        value: templates.join(","),
      }),
    );

    // Append the form to the body and submit it
    form.appendTo("body").submit();
  };

  // DataTable Layout and Buttons
  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [4, 8, 9, 10],
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

  if (templateNumber > 10) {
    const menu = [10];
    if (templateNumber > 25) menu.push(25);
    if (templateNumber > 50) menu.push(50);
    if (templateNumber > 100) menu.push(100);
    menu.push({ label: t("datatable.length_all", "All"), value: -1 }); // Translate "All"
    layout.bottomStart = {
      pageLength: { menu: menu },
      info: true,
    };
    layout.bottomEnd.paging = true;
  }

  layout.topStart.buttons = [
    {
      extend: "create_template",
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
        let translatedTitle = title; // Fallback

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
          filename: "bw_templates",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
          filename: "bw_templates",
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
          extend: "delete_templates", // Text defined in custom button below
          className: "text-danger",
        },
      ],
    },
  ];

  // Modal cleanup
  $("#modal-delete-templates").on("hidden.bs.modal", function () {
    $("#selected-templates").empty();
    $("#selected-templates-input").val("");
  });

  // Function to get selected template ids
  const getSelectedTemplates = () => {
    const templates = [];
    $("tr.selected").each(function () {
      templates.push($(this).find("td:eq(2)").text().trim()); // Assuming id is in 3rd column (index 2)
    });
    return templates;
  };

  // Custom Button Definitions
  $.fn.dataTable.ext.buttons.create_template = {
    text: `<span class="tf-icons bx bx-plus"></span><span class="d-none d-md-inline" data-i18n="button.create_template"> ${t(
      "button.create_template",
      "Create new template",
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
      const basePath = window.location.pathname.replace(/\/$/, "");
      window.location.href = `${basePath}/new`;
    },
  };

  $.fn.dataTable.ext.buttons.delete_templates = {
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
      $(".dt-button-background").click(); // Close collection dropdown

      const templates = getSelectedTemplates();
      if (templates.length === 0) {
        actionLock = false;
        return;
      }
      setupDeletionModal(templates);
      actionLock = false; // Release lock after modal setup
    },
  };

  const templates_config = {
    tableSelector: "#templates",
    tableName: "templates",
    columnVisibilityCondition: (column) => column > 2 && column < 9,
    dataTableOptions: {
      columnDefs: [
        { orderable: false, className: "dtr-control", targets: 0 },
        { orderable: false, render: DataTable.render.select(), targets: 1 },
        { orderable: false, targets: -1 },
        { visible: false, targets: [3] },
        {
          targets: [9, 10],
          render: function (data, type, row) {
            if (type === "display" || type === "filter") {
              const date = new Date(data);
              if (data && !isNaN(date.getTime())) {
                return date.toLocaleString();
              }
            }
            return data || "";
          },
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.plugin", "Plugin"),
            combiner: "or",
          },
          targets: 4,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.method", "Method"),
            combiner: "or",
          },
          targets: 8,
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
                  new Date() - new Date(rowData[9]) < 86400000,
              },
              {
                label: `<span data-i18n="searchpane.last_7d">${t(
                  "searchpane.last_7d",
                  "Last 7 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[9]) < 604800000,
              },
              {
                label: `<span data-i18n="searchpane.last_30d">${t(
                  "searchpane.last_30d",
                  "Last 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[9]) < 2592000000,
              },
              {
                label: `<span data-i18n="searchpane.older_30d">${t(
                  "searchpane.older_30d",
                  "More than 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[9]) >= 2592000000,
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 9,
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
                  new Date() - new Date(rowData[10]) < 86400000,
              },
              {
                label: `<span data-i18n="searchpane.last_7d">${t(
                  "searchpane.last_7d",
                  "Last 7 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[10]) < 604800000,
              },
              {
                label: `<span data-i18n="searchpane.last_30d">${t(
                  "searchpane.last_30d",
                  "Last 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[10]) < 2592000000,
              },
              {
                label: `<span data-i18n="searchpane.older_30d">${t(
                  "searchpane.older_30d",
                  "More than 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[10]) >= 2592000000,
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 10,
        },
      ],
      order: [[10, "desc"]],
      autoFill: false,
      responsive: true,
      select: {
        style: "multi+shift",
        selector: "td:nth-child(2)",
        headerCheckbox: true,
      },
      layout: layout,
      initComplete: function (settings, json) {
        $("#templates_wrapper .btn-secondary").removeClass("btn-secondary");
        if (isReadOnly) {
          const titleKey = userReadOnly
            ? "tooltip.readonly_user_action_disabled"
            : "tooltip.readonly_db_action_disabled"; // Assuming DB read-only prevents creation
          const defaultTitle = userReadOnly
            ? "Your account is readonly, action disabled."
            : "The database is in readonly, action disabled.";
          $("#templates_wrapper .dt-buttons")
            .attr(
              "data-bs-original-title",
              t(titleKey, defaultTitle, {
                action: t("button.create_template"),
              }), // Pass action name
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
    }).then(() => initializeDataTable(templates_config));
  }

  $(document).on("click", ".delete-template", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    if (actionLock) return; // Prevent overlapping actions
    actionLock = true; // Lock action

    const template = $(this).data("template-id");
    setupDeletionModal([template]);
    actionLock = false; // Unlock after modal setup
  });
});
