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
  const instanceNumber = parseInt($("#instances_number").val());
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const userReadOnly = $("#user-read-only").val().trim() === "True";

  const pingInstances = (instances) => {
    showLoadingModal = true;

    setTimeout(() => {
      if (actionLock && showLoadingModal) {
        $(".dt-button-background").click();
        $("#loadingModal").modal("show");
        setTimeout(() => {
          $("#loadingModal").modal("hide");
        }, 5000);
      }
    }, 500);

    // Create a FormData object
    const formData = new FormData();
    formData.append("csrf_token", $("#csrf_token").val());
    formData.append("instances", instances.join(","));

    // Send the form data using $.ajax
    $.ajax({
      url: `${window.location.pathname}/ping`,
      type: "POST",
      data: formData,
      processData: false,
      contentType: false,
      success: function (data) {
        data.failed.forEach((instance) => {
          var feedbackToastFailed = $("#feedback-toast").clone();
          feedbackToastFailed.attr("id", `feedback-toast-${toastNum++}`);
          feedbackToastFailed.addClass("border-danger");
          feedbackToastFailed.find(".toast-header").addClass("text-danger");
          // Translate toast header and body
          feedbackToastFailed
            .find("span")
            .text(t("toast.header.ping_failed", "Ping failed"));
          feedbackToastFailed.find("div.toast-body").text(instance.message);
          feedbackToastFailed.appendTo("#feedback-toast-container");
          feedbackToastFailed.toast("show");
        });

        if (data.succeed.length > 0) {
          var feedbackToastSucceed = $("#feedback-toast").clone();
          feedbackToastSucceed.attr("id", `feedback-toast-${toastNum++}`);
          feedbackToastSucceed.addClass("border-primary");
          feedbackToastSucceed.find(".toast-header").addClass("text-primary");
          feedbackToastSucceed
            .find("span")
            .text(t("toast.header.ping_succeed", "Ping successful"));
          feedbackToastSucceed.find("div.toast-body").text(
            t("toast.body.ping_succeed", "Instances: {{instances}}", {
              instances: data.succeed.join(", "),
            }),
          );
          feedbackToastSucceed.appendTo("#feedback-toast-container");
          feedbackToastSucceed.toast("show");
        }
      },
      error: function (xhr, status, error) {
        console.error("AJAX request failed:", status, error);
        // Translate error alert
        alert(
          t(
            "alert.ping_error",
            "An error occurred while pinging the instances.",
          ),
        );
      },
      complete: function () {
        actionLock = false;
        showLoadingModal = false;
        $("#loadingModal").modal("hide");
      },
    });
  };

  const setupDeletionModal = (instances) => {
    const delete_modal = $("#modal-delete-instances");
    const $modalBody = $("#selected-instances");
    $modalBody.empty(); // Clear previous content

    $("#selected-instances-input").val(instances.join(","));

    const $header = $(`
      <ul class="list-group list-group-horizontal w-100">
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold" data-i18n="table.header.hostname">${t(
              "table.header.hostname",
              "Hostname",
            )}</div>
          </div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="fw-bold" data-i18n="table.header.health">${t(
            "table.header.health",
            "Health",
          )}</div>
        </li>
      </ul>`);
    $modalBody.append($header);

    instances.forEach((instance) => {
      const $row = $(
        `<ul class="list-group list-group-horizontal w-100"></ul>`,
      );

      // Hostname item
      const $hostnameItem = $(`<li class="list-group-item" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold">${instance}</div>
          </div>
        </li>`);
      $row.append($hostnameItem);

      // Clone the status element and append it
      const statusClone = $("#status-" + instance.replaceAll(".", "_")).clone(); // Ensure ID is valid
      const $statusListItem = $(
        `<li class="list-group-item" style="flex: 1 0;"></li>`,
      );
      $statusListItem.append(statusClone.removeClass("highlight")); // Remove highlight if present
      $row.append($statusListItem);

      $modalBody.append($row);
    });

    // Use plural/singular i18n key for alert
    const alertTextKey =
      instances.length > 1
        ? "modal.body.delete_confirmation_alert_plural"
        : "modal.body.delete_confirmation_alert";
    const defaultAlertText = `Are you sure you want to delete the selected instance${
      instances.length > 1 ? "s" : ""
    }?`;
    delete_modal.find(".alert").text(t(alertTextKey, defaultAlertText));

    const modalInstance = new bootstrap.Modal(delete_modal[0]);
    modalInstance.show();
  };

  const execForm = (instances, action) => {
    // Create a form element using jQuery and set its attributes
    const form = $("<form>", {
      method: "POST",
      action: `${window.location.pathname}/${action}`, // Action like 'reload', 'stop'
      class: "visually-hidden",
    });

    // Add CSRF token and instances as hidden inputs
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
        name: "instances",
        value: instances.join(","),
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
        columns: [4, 5, 6, 7, 8], // Adjust if columns change: Version, Status, Type, First Seen, Last Seen
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

  if (instanceNumber > 10) {
    const menu = [10];
    if (instanceNumber > 25) menu.push(25);
    if (instanceNumber > 50) menu.push(50);
    if (instanceNumber > 100) menu.push(100);
    menu.push({ label: t("datatable.length_all", "All"), value: -1 }); // Translate "All"
    layout.bottomStart = {
      pageLength: { menu: menu },
      info: true,
    };
    layout.bottomEnd.paging = true;
  }

  layout.topStart.buttons = [
    {
      extend: "create_instance",
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
          filename: "bw_instances",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
          filename: "bw_instances",
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
          extend: "ping_instances", // Text defined in custom button below
        },
        {
          extend: "exec_form",
          text: `<span class="tf-icons bx bx-refresh bx-18px me-2"></span><span data-i18n="button.reload">${t(
            "button.reload",
            "Reload",
          )}</span>`,
        },
        {
          extend: "exec_form",
          text: `<span class="tf-icons bx bx-stop bx-18px me-2"></span><span data-i18n="button.stop">${t(
            "button.stop",
            "Stop",
          )}</span>`,
        },
        {
          extend: "delete_instances", // Text defined in custom button below
          className: "text-danger",
        },
      ],
    },
  ];

  // Modal cleanup
  $("#modal-delete-instances").on("hidden.bs.modal", function () {
    $("#selected-instances").empty();
    $("#selected-instances-input").val("");
  });

  // Function to get selected instance hostnames
  const getSelectedInstances = () => {
    const instances = [];
    $("tr.selected").each(function () {
      instances.push($(this).find("td:eq(2)").text().trim()); // Assuming hostname is in 3rd column (index 2)
    });
    return instances;
  };

  // Custom Button Definitions
  $.fn.dataTable.ext.buttons.create_instance = {
    text: `<span class="tf-icons bx bx-plus"></span><span class="d-none d-md-inline" data-i18n="button.create_instance"> ${t(
      "button.create_instance",
      "Create new instance",
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
      const modal = new bootstrap.Modal($("#modal-create-instance"));
      modal.show();

      $("#modal-create-instance").on("shown.bs.modal", function () {
        $(this).find("#hostname").focus();
      });
    },
  };

  $.fn.dataTable.ext.buttons.ping_instances = {
    text: `<span class="tf-icons bx bx-bell bx-18px me-2"></span><span data-i18n="button.ping">${t(
      "button.ping",
      "Ping",
    )}</span>`,
    action: function (e, dt, node, config) {
      if (actionLock) return;
      actionLock = true;

      const instances = getSelectedInstances();
      if (instances.length === 0) {
        actionLock = false;
        return;
      }
      pingInstances(instances);
    },
  };

  $.fn.dataTable.ext.buttons.exec_form = {
    action: function (e, dt, node, config) {
      if (actionLock) return;
      actionLock = true;

      const instances = getSelectedInstances();
      if (instances.length === 0) {
        actionLock = false;
        return;
      }

      // Determine action based on icon class in the button's text definition
      const bxIconClass = node.find("span.bx").attr("class");
      let action;
      if (bxIconClass && bxIconClass.includes("bx-refresh")) {
        action = "reload";
      } else if (bxIconClass && bxIconClass.includes("bx-stop")) {
        action = "stop";
      } else {
        console.warn("Could not determine action for exec_form button.");
        actionLock = false;
        return;
      }

      execForm(instances, action);
      // actionLock will be released by page reload/navigation
    },
  };

  $.fn.dataTable.ext.buttons.delete_instances = {
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

      const instances = getSelectedInstances();
      if (instances.length === 0) {
        actionLock = false;
        return;
      }
      setupDeletionModal(instances);
      actionLock = false; // Release lock after modal setup
    },
  };

  const instances_config = {
    tableSelector: "#instances",
    tableName: "instances",
    columnVisibilityCondition: (column) => column > 2 && column < 9,
    dataTableOptions: {
      columnDefs: [
        { orderable: false, className: "dtr-control", targets: 0 },
        { orderable: false, render: DataTable.render.select(), targets: 1 },
        { orderable: false, targets: -1 },
        { visible: false, targets: [3, 4] },
        {
          targets: [7, 8],
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
            header: t("searchpane.method", "Method"),
            combiner: "or",
          },
          targets: 4,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.health", "Health"),
            options: [
              {
                label: `<i class="bx bx-xs bx-up-arrow-alt text-success"></i> <span data-i18n="status.up">${t(
                  "status.up",
                  "Up",
                )}</span>`,
                value: function (rowData, rowIdx) {
                  return rowData[5].includes("status.up");
                },
              },
              {
                label: `<i class="bx bx-xs bx-down-arrow-alt text-danger"></i> <span data-i18n="status.down">${t(
                  "status.down",
                  "Down",
                )}</span>`,
                value: function (rowData, rowIdx) {
                  return rowData[5].includes("status.down");
                },
              },
              {
                label: `<i class="bx bx-xs bxs-hourglass text-warning"></i> <span data-i18n="status.loading">${t(
                  "status.loading",
                  "Loading",
                )}</span>`,
                value: function (rowData, rowIdx) {
                  return rowData[5].includes("status.loading");
                },
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
            header: t("searchpane.type", "Type"),
            options: [
              {
                label: `<i class="bx bx-xs bx-microchip"></i> <span data-i18n="instance.type.static">${t(
                  "instance.type.static",
                  "Static",
                )}</span>`,
                value: (rowData) => rowData[6].includes("instance.type.static"),
              },
              {
                label: `<i class="bx bx-xs bxl-docker"></i> <span data-i18n="instance.type.container">${t(
                  "instance.type.container",
                  "Container",
                )}</span>`,
                value: (rowData) =>
                  rowData[6].includes("instance.type.container"),
              },
              {
                label: `<i class="bx bx-xs bxl-kubernetes"></i> <span data-i18n="instance.type.pod">${t(
                  "instance.type.pod",
                  "Pod",
                )}</span>`,
                value: (rowData) => rowData[6].includes("instance.type.pod"),
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
            header: t("searchpane.first_seen", "First Seen"),
            options: [
              {
                label: `<span data-i18n="searchpane.last_24h">${t(
                  "searchpane.last_24h",
                  "Last 24 hours",
                )}</span>`,
                value: (rowData) =>
                  rowData[7] && new Date() - new Date(rowData[7]) < 86400000, // 24h
              },
              {
                label: `<span data-i18n="searchpane.last_7d">${t(
                  "searchpane.last_7d",
                  "Last 7 days",
                )}</span>`,
                value: (rowData) =>
                  rowData[7] && new Date() - new Date(rowData[7]) < 604800000, // 7d
              },
              {
                label: `<span data-i18n="searchpane.last_30d">${t(
                  "searchpane.last_30d",
                  "Last 30 days",
                )}</span>`,
                value: (rowData) =>
                  rowData[7] && new Date() - new Date(rowData[7]) < 2592000000, // 30d
              },
              {
                label: `<span data-i18n="searchpane.older_30d">${t(
                  "searchpane.older_30d",
                  "More than 30 days",
                )}</span>`,
                value: (rowData) =>
                  rowData[7] && new Date() - new Date(rowData[7]) >= 2592000000,
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
            header: t("searchpane.last_seen", "Last Seen"),
            options: [
              {
                label: `<span data-i18n="searchpane.last_24h">${t(
                  "searchpane.last_24h",
                  "Last 24 hours",
                )}</span>`,
                value: (rowData) =>
                  rowData[8] && new Date() - new Date(rowData[8]) < 86400000,
              },
              {
                label: `<span data-i18n="searchpane.last_7d">${t(
                  "searchpane.last_7d",
                  "Last 7 days",
                )}</span>`,
                value: (rowData) =>
                  rowData[8] && new Date() - new Date(rowData[8]) < 604800000,
              },
              {
                label: `<span data-i18n="searchpane.last_30d">${t(
                  "searchpane.last_30d",
                  "Last 30 days",
                )}</span>`,
                value: (rowData) =>
                  rowData[8] && new Date() - new Date(rowData[8]) < 2592000000,
              },
              {
                label: `<span data-i18n="searchpane.older_30d">${t(
                  "searchpane.older_30d",
                  "More than 30 days",
                )}</span>`,
                value: (rowData) =>
                  rowData[8] && new Date() - new Date(rowData[8]) >= 2592000000,
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 8,
        },
      ],
      order: [[8, "desc"]],
      autoFill: false,
      responsive: true,
      select: {
        style: "multi+shift",
        selector: "td:nth-child(2)",
        headerCheckbox: true,
      },
      layout: layout,
      initComplete: function (settings, json) {
        $("#instances_wrapper .btn-secondary").removeClass("btn-secondary");
        if (isReadOnly) {
          const titleKey = userReadOnly
            ? "tooltip.readonly_user_action_disabled"
            : "tooltip.readonly_db_action_disabled"; // Assuming DB read-only prevents creation
          const defaultTitle = userReadOnly
            ? "Your account is readonly, action disabled."
            : "The database is in readonly, action disabled.";
          $("#instances_wrapper .dt-buttons")
            .attr(
              "data-bs-original-title",
              t(titleKey, defaultTitle, {
                action: t("button.create_instance"),
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
    }).then(() => initializeDataTable(instances_config));
  }

  // Event handlers for individual row actions
  $(document).on("click", ".ping-instance", function () {
    if (actionLock) return;
    actionLock = true;
    const instance = $(this).data("instance");
    pingInstances([instance]);
  });

  $(document).on("click", ".reload-instance, .stop-instance", function () {
    // No read-only check here as these actions interact with instances directly, not DB usually
    // But actionLock prevents simultaneous actions
    if (actionLock) return;
    actionLock = true; // Lock action

    const instance = $(this).data("instance");
    const action = $(this).hasClass("reload-instance") ? "reload" : "stop";
    execForm([instance], action);
    // actionLock released by page navigation
  });

  $(document).on("click", ".delete-instance", function () {
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

    const instance = $(this).data("instance");
    setupDeletionModal([instance]);
    actionLock = false; // Unlock after modal setup
  });
});
