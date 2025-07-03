$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key; // Fallback

  var actionLock = false;
  const dragArea = $("#drag-area");
  const fileInput = $("#file-input");
  const fileList = $("#file-list");
  const pluginNumber = parseInt($("#plugins_number").val());
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const userReadOnly = $("#user-read-only").val().trim() === "True";

  const setupDeletionModal = (plugins) => {
    const delete_modal = $("#modal-delete-plugins");
    const list = $(
      `<ul class="list-group list-group-horizontal w-100">
      <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
        <div class="ms-2 me-auto">
          <div class="fw-bold" data-i18n="table.header.name">${t(
            "table.header.name",
            "Name",
          )}</div>
        </div>
      </li>
      <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
        <div class="fw-bold" data-i18n="table.header.version">${t(
          "table.header.version",
          "Version",
        )}</div>
      </li>
      <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
        <div class="fw-bold" data-i18n="table.header.type">${t(
          "table.header.type",
          "Type",
        )}</div>
      </li>
      </ul>`,
    );
    $("#selected-plugins-delete").append(list);

    plugins.forEach((plugin) => {
      const list = $(
        `<ul class="list-group list-group-horizontal w-100"></ul>`,
      );

      // Create the list item using template literals
      const listItem = $(`<li class="list-group-item" style="flex: 1 1 0;">
  <div class="ms-2 me-auto">
    ${$(`#name-${plugin}`).html()}
  </div>
</li>`);
      list.append(listItem);

      // Clone the version element and append it to the list item
      const versionClone = $(`#version-${plugin}`).clone();
      const versionListItem = $(
        `<li class="list-group-item" style="flex: 1 1 0;"></li>`,
      );
      versionListItem.append(versionClone.removeClass("highlight"));
      list.append(versionListItem);

      // Clone the type element and append it to the list item
      const typeClone = $(`#type-${plugin}`).clone();
      const typeListItem = $(
        `<li class="list-group-item" style="flex: 1 1 0;"></li>`,
      );
      typeListItem.append(typeClone.removeClass("highlight"));
      list.append(typeListItem);
      typeClone.find('[data-bs-toggle="tooltip"]').tooltip();

      $("#selected-plugins-delete").append(list);
    });

    const modal = new bootstrap.Modal(delete_modal);
    delete_modal
      .find(".alert")
      .text(
        t(
          plugins.length > 1
            ? "modal.body.delete_confirmation_alert_plural"
            : "modal.body.delete_confirmation_alert",
          `Are you sure you want to delete the selected plugin${"s".repeat(
            plugins.length > 1,
          )}?`,
        ),
      );
    modal.show();

    $("#selected-plugins-input-delete").val(plugins.join(","));
  };

  // Function to validate plugin files
  const validateFile = (file) => {
    const validExtensions = [".zip", ".tar.gz", ".tar.xz"];
    const fileName = file.name.toLowerCase();
    const maxFileSize = 50 * 1024 * 1024; // 50 MB

    const isValidExtension = validExtensions.some(function (ext) {
      return fileName.endsWith(ext);
    });

    if (!isValidExtension) {
      return false;
    }

    if (file.size > maxFileSize) {
      alert("File size exceeds 50 MB limit.");
      return false;
    }

    return true;
  };

  const uploadFile = (file) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("csrf_token", $("#csrf_token").val());

    // Construct the upload URL
    const currentUrl = window.location.href.split("?")[0].split("#")[0];
    const uploadUrl = currentUrl.replace(/\/$/, "") + "/upload";

    const fileSize = (file.size / 1024).toFixed(2);
    const fileItem = $(`
            <div class="file-item">
                <strong>${file.name}</strong> (${fileSize} KB)
            </div>
        `);
    fileList.append(fileItem);

    const progressBar = $(
      '<div class="progress-bar" role="progressbar" style="width: 0%;"></div>',
    );
    const progress = $('<div class="progress mt-2"></div>').append(progressBar);
    fileList.append(progress);

    $.ajax({
      url: uploadUrl,
      type: "POST",
      data: formData,
      processData: false,
      contentType: false,
      xhr: function () {
        const xhr = new window.XMLHttpRequest();
        xhr.upload.addEventListener(
          "progress",
          (evt) => {
            if (evt.lengthComputable) {
              const percentComplete = (evt.loaded / evt.total) * 100;
              progressBar.css("width", percentComplete + "%");
              progressBar.attr("aria-valuenow", percentComplete);
            }
          },
          false,
        );
        return xhr;
      },
      success: function () {
        progressBar.addClass("bg-success");
        $("#add-plugins-submit").removeClass("disabled");
        fileItem.append('<span class="text-success ms-2">Uploaded</span>');
      },
      error: function () {
        progressBar.addClass("bg-danger");
        fileItem.append('<span class="text-danger ms-2">Failed</span>');
        alert("An error occurred while uploading the file. Please try again.");
      },
    });
  };

  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [6, 7, 8],
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

  if (pluginNumber > 10) {
    const menu = [10];
    if (pluginNumber > 25) {
      menu.push(25);
    }
    if (pluginNumber > 50) {
      menu.push(50);
    }
    if (pluginNumber > 100) {
      menu.push(100);
    }
    menu.push({ label: "All", value: -1 });
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
      extend: "add_plugin",
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
          filename: "bw_plugins",
          exportOptions: {
            modifier: {
              search: "none",
            },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
          filename: "bw_plugins",
          exportOptions: {
            modifier: {
              search: "none",
            },
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
          extend: "delete_plugins",
          className: "text-danger",
        },
      ],
    },
  ];

  $("#modal-delete-plugins").on("hidden.bs.modal", function () {
    $("#selected-plugins-delete").empty();
    $("#selected-plugins-input-delete").val("");
  });

  const getSelectedPlugins = () => {
    const plugins = [];
    $("tr.selected").each(function () {
      const plugin = $(this).find("td:eq(2)").data("id");
      if (plugin) {
        plugins.push(plugin);
      }
    });
    return plugins;
  };

  $.fn.dataTable.ext.buttons.add_plugin = {
    text: `<span class="tf-icons bx bx-plus"></span><span class="d-none d-md-inline" data-i18n="button.add_plugin_plural"> ${t(
      "button.add_plugin_plural",
      "Add plugin(s)",
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
      const plugin_modal = $("#modal-add-plugins");
      const modal = new bootstrap.Modal(plugin_modal);
      modal.show();
    },
  };

  $.fn.dataTable.ext.buttons.delete_plugins = {
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
      if (actionLock) {
        return;
      }
      actionLock = true;
      $(".dt-button-background").click();

      const plugins = getSelectedPlugins();
      if (plugins.length === 0) {
        actionLock = false;
        return;
      }

      setupDeletionModal(plugins);

      actionLock = false;
    },
  };

  const plugins_config = {
    tableSelector: "#plugins",
    tableName: "plugins",
    columnVisibilityCondition: (column) =>
      column > 1 && column !== 3 && column < 9,
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
        {
          orderable: false,
          targets: -1,
        },
        {
          visible: false,
          targets: [2, 4],
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.stream", "Stream"),
            options: [
              {
                label: `<i class="bx bx-xs bx-x text-danger"></i>&nbsp;<span data-i18n="status.no">${t(
                  "status.no",
                  "No",
                )}</span>`,
                value: function (rowData, rowIdx) {
                  return rowData[6].includes("bx-x");
                },
              },
              {
                label: `<i class="bx bx-xs bx-check text-success"></i>&nbsp;<span data-i18n="status.yes">${t(
                  "status.yes",
                  "Yes",
                )}</span>`,
                value: function (rowData, rowIdx) {
                  return rowData[6].includes("bx-check");
                },
              },
              {
                label: `<i class="bx bx-xs bx-minus text-warning"></i>&nbsp;<span data-i18n="status.partial">${t(
                  "status.partial",
                  "Partial",
                )}</span>`,
                value: function (rowData, rowIdx) {
                  return rowData[6].includes("bx-minus");
                },
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
            header: t("searchpane.type", "Type"),
            options: [
              {
                label: `<img src="${$("#pro_diamond_url")
                  .val()
                  .trim()}" alt="Pro plugin" width="16px" height="12.9125px" class="mb-1">&nbsp;<span data-i18n="plugin.type.pro">${t(
                  "plugin.type.pro",
                  "PRO",
                )}</span>`,
                value: function (rowData, rowIdx) {
                  return rowData[7].includes("plugin.type.pro");
                },
              },
              {
                label:
                  '<i class="bx bx-xs bx-plug"></i>&nbsp;<span data-i18n="plugin.type.external">' +
                  t("plugin.type.external", "EXTERNAL") +
                  "</span>",
                value: function (rowData, rowIdx) {
                  return rowData[7].includes("plugin.type.external");
                },
              },
              {
                label:
                  '<i class="bx bx-xs bx-cloud-upload"></i>&nbsp;<span data-i18n="plugin.type.ui">' +
                  t("plugin.type.ui", "UI") +
                  "</span>",
                value: function (rowData, rowIdx) {
                  return rowData[7].includes("plugin.type.ui");
                },
              },
              {
                label:
                  '<i class="bx bx-xs bx-shield"></i>&nbsp;<span data-i18n="plugin.type.core">' +
                  t("plugin.type.core", "CORE") +
                  "</span>",
                value: function (rowData, rowIdx) {
                  return rowData[7].includes("plugin.type.core");
                },
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
            header: t("searchpane.method", "Method"),
            combiner: "or",
            orderable: false,
          },
          targets: 8,
        },
      ],
      order: [[3, "asc"]],
      autoFill: false,
      responsive: true,
      select: {
        style: "multi+shift",
        selector: "td:nth-child(2)",
        headerCheckbox: true,
      },
      layout: layout,
      initComplete: function (settings, json) {
        $("#plugins_wrapper .btn-secondary").removeClass("btn-secondary");
        if (isReadOnly)
          $("#plugins_wrapper .dt-buttons")
            .attr(
              "data-bs-original-title",
              `${
                userReadOnly
                  ? t(
                      "tooltip.readonly_user_action_disabled",
                      "Your account is readonly, action disabled.",
                    )
                  : t(
                      "tooltip.readonly_db_action_disabled",
                      "The database is in readonly, action disabled.",
                    )
              }`,
            )
            .attr("data-bs-placement", "right")
            .tooltip();
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
    }).then(() => initializeDataTable(plugins_config));
  }

  $(document).on("click", ".delete-plugin", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const $this = $(this);
    setupDeletionModal([$this.data("plugin-id")]);
  });

  // Open file dialog on click
  dragArea.on("click", function () {
    fileInput.click();
  });

  // Handle drag over
  dragArea.on("dragover", function (e) {
    e.preventDefault();
    dragArea.removeClass("border-dashed");
    dragArea.addClass("bg-primary text-white");
    dragArea.find("i").removeClass("text-primary");
  });

  // Handle drag leave
  dragArea.on("dragleave", function (e) {
    e.preventDefault();
    dragArea.addClass("border-dashed");
    dragArea.removeClass("bg-primary text-white");
    dragArea.find("i").addClass("text-primary");
  });

  // File input change event
  fileInput.on("change", function () {
    const files = this.files;
    for (let i = 0; i < files.length; i++) {
      setTimeout(() => {
        const file = files[i];
        if (validateFile(file)) {
          uploadFile(file);
        } else {
          alert("Please upload a valid plugin file (.zip, .tar.gz, .tar.xz).");
        }
      }, 500 * i);
    }
  });

  // Handle drop
  dragArea.on("drop", function (e) {
    e.preventDefault();
    dragArea.addClass("border-dashed");
    dragArea.removeClass("bg-primary text-white");
    dragArea.find("i").addClass("text-primary");
    fileInput.prop("files", e.originalEvent.dataTransfer.files);
    fileInput.trigger("change");
  });
});
