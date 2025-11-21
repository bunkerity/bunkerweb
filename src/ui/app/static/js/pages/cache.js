$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key; // Fallback

  const cacheNumber = parseInt($("#cache_number").val());
  const services = $("#services").val().trim().split(" ");
  const cacheServiceSelection = $("#cache_service_selection").val().trim();
  const cachePluginSelection = $("#cache_plugin_selection").val().trim();
  const cacheJobNameSelection = $("#cache_job_name_selection").val().trim();
  const isReadOnly = $("#is-read-only").val().trim() === "True";

  var actionLock = false;

  const setupDeletionModal = (cacheFiles) => {
    const delete_modal = $("#modal-delete-cache");
    const $modalBody = $("#selected-cache-delete");
    $modalBody.empty(); // Clear previous content

    // Create and append the header row with translated headers
    const $header = $(`
      <ul class="list-group list-group-horizontal w-100">
        <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold" data-i18n="table.header.file_name">${t(
              "table.header.file_name",
              "File name",
            )}</div>
          </div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
          <div class="fw-bold" data-i18n="table.header.job_name">${t(
            "table.header.job_name",
            "Job name",
          )}</div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
          <div class="fw-bold" data-i18n="table.header.plugin">${t(
            "table.header.plugin",
            "Plugin",
          )}</div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
          <div class="fw-bold" data-i18n="table.header.service">${t(
            "table.header.service",
            "Service",
          )}</div>
        </li>
      </ul>`);
    $modalBody.append($header);

    cacheFiles.forEach((cache) => {
      const list = $(
        `<ul class="list-group list-group-horizontal w-100"></ul>`,
      );

      // Create the list items using the actual HTML content from the table
      const fileNameItem = $(`<li class="list-group-item" style="flex: 1 1 0;">
          <div class="ms-2 me-auto">
            ${cache.fileNameHtml}
          </div>
        </li>`);
      list.append(fileNameItem);

      const jobNameItem = $(
        `<li class="list-group-item" style="flex: 1 1 0;">
          ${cache.jobNameHtml}
        </li>`,
      );
      list.append(jobNameItem);

      const pluginItem = $(
        `<li class="list-group-item" style="flex: 1 1 0;">
          ${cache.pluginHtml}
        </li>`,
      );
      list.append(pluginItem);

      const serviceItem = $(
        `<li class="list-group-item" style="flex: 1 1 0;">
          ${cache.serviceHtml}
        </li>`,
      );
      list.append(serviceItem);

      $modalBody.append(list);
    });

    const modalInstance = new bootstrap.Modal(delete_modal[0]);

    // Update the alert text using i18next
    const alertTextKey =
      cacheFiles.length > 1
        ? "modal.body.confirm_cache_deletion_alert_plural"
        : "modal.body.confirm_cache_deletion_alert";
    delete_modal
      .find(".alert")
      .attr("data-i18n", alertTextKey)
      .text(
        t(
          alertTextKey,
          `Are you sure you want to delete the selected cache file${
            cacheFiles.length > 1 ? "s" : ""
          }?`,
        ),
      );
    modalInstance.show();

    // Prepare data for submission (only text values for backend)
    const backendData = cacheFiles.map((cache) => ({
      fileName: cache.fileName,
      jobName: cache.jobName,
      plugin: cache.plugin,
      service: cache.service,
    }));
    $("#selected-cache-input-delete").val(JSON.stringify(backendData));
  };

  const servicesSearchPanesOptions = [
    {
      label: "global",
      value: function (rowData) {
        return $(rowData[5]).text().trim() === "global";
      },
    },
  ];

  services.forEach((service) => {
    servicesSearchPanesOptions.push({
      label: service,
      value: function (rowData) {
        return $(rowData[5]).text().trim() === service;
      },
    });
  });

  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [3, 4, 5, 6],
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

  if (cacheNumber > 10) {
    const menu = [10];
    if (cacheNumber > 25) {
      menu.push(25);
    }
    if (cacheNumber > 50) {
      menu.push(50);
    }
    if (cacheNumber > 100) {
      menu.push(100);
    }
    menu.push({ label: t("datatable.length_all", "All"), value: -1 });
    layout.bottomStart = {
      pageLength: {
        menu: menu,
      },
      info: true,
    };
    layout.bottomEnd.paging = true;
  }

  const getSelectedCacheFiles = () => {
    const cacheFiles = [];
    $("#cache tbody tr.selected").each(function () {
      const $row = $(this);
      const fileNameHtml = $row.find("td:eq(2)").html();
      const jobNameHtml = $row.find("td:eq(3)").html();
      const pluginHtml = $row.find("td:eq(4)").html();
      const serviceHtml = $row.find("td:eq(5)").html();

      // Also get text content for backend submission
      const fileName = $row.find("td:eq(2)").find("a").text().trim();
      const jobName = $row.find("td:eq(3)").text().trim();
      const plugin = $row.find("td:eq(4)").text().trim();
      let service;
      const $serviceCell = $row.find("td:eq(5)");
      const $serviceLink = $serviceCell.find("a");
      if ($serviceLink.length > 0) {
        service = $serviceLink.text().trim();
      } else {
        const $serviceSpan = $serviceCell.find("span");
        if (
          $serviceSpan.length &&
          $serviceSpan.attr("data-i18n") === "scope.global"
        ) {
          service = "global"; // Normalize translated global to actual value
        } else {
          service = $serviceSpan.length
            ? $serviceSpan.text().trim()
            : $serviceCell.text().trim();
        }
      }

      cacheFiles.push({
        fileName,
        jobName,
        plugin,
        service,
        fileNameHtml,
        jobNameHtml,
        pluginHtml,
        serviceHtml,
      });
    });
    return cacheFiles;
  };

  $.fn.dataTable.ext.buttons.delete_cache = {
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

      const cacheFiles = getSelectedCacheFiles();
      if (cacheFiles.length === 0) {
        actionLock = false;
        return;
      }
      setupDeletionModal(cacheFiles);
      actionLock = false;
    },
  };

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
        const headerCell = dt.column(idx).header(); // Get header cell DOM element
        const $header = $(headerCell);
        // Find the element with data-i18n (likely a span inside the th)
        const $translatableElement = $header.find("[data-i18n]");
        let i18nKey = $translatableElement.data("i18n");
        let translatedTitle = title; // Use original title as fallback

        if (i18nKey) {
          translatedTitle = t(i18nKey, title); // Pass original title as defaultValue
        } else {
          translatedTitle = $header.text().trim() || title; // Use text content or DT title
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
            columns: ":visible:not(:first-child):not(:last-child)",
          },
        },
        {
          extend: "csv",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV',
          bom: true,
          filename: "bw_cache",
          exportOptions: {
            modifier: {
              search: "none",
            },
            columns: ":not(:first-child):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel',
          filename: "bw_cache",
          exportOptions: {
            modifier: {
              search: "none",
            },
            columns: ":not(:first-child):not(:last-child)",
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
          extend: "delete_cache",
          className: "text-danger",
        },
      ],
    },
  ];

  const cache_table = initializeDataTable({
    tableSelector: "#cache",
    tableName: "cache",
    columnVisibilityCondition: (column) => 3 < column && column < 8,
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
          targets: 6,
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
            header: t("searchpane.job_name", "Job name"),
            combiner: "or",
          },
          targets: 3,
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
            header: t("searchpane.service", "Service"),
            combiner: "or",
            options: servicesSearchPanesOptions,
          },
          targets: 5,
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
      ],
      order: [[4, "asc"]],
      autoFill: false,
      responsive: true,
      select: {
        style: "multi+shift",
        selector: "td:nth-child(2)",
        headerCheckbox: true,
      },
      layout: layout,
      initComplete: function (settings, json) {
        $("#cache_wrapper .btn-secondary").removeClass("btn-secondary");
      },
    },
  });

  $(`#DataTables_Table_0 span[title='${cacheJobNameSelection}']`).trigger(
    "click",
  );

  $(`#DataTables_Table_1 span[title='${cachePluginSelection}']`).trigger(
    "click",
  );

  $(`#DataTables_Table_2 span[title='${cacheServiceSelection}']`).trigger(
    "click",
  );

  if (cacheJobNameSelection || cachePluginSelection || cacheServiceSelection) {
    cache_table.searchPanes.container().show();
    if (typeof cache_table.updateFilterToggleUI === "function") {
      cache_table.updateFilterToggleUI(true);
    } else if (cache_table.filterToggleSelectors) {
      const selectors = cache_table.filterToggleSelectors;
      if (selectors.show) $(selectors.show).addClass("d-none");
      if (selectors.hide) $(selectors.hide).removeClass("d-none");
    }
  }

  // Modal event handlers
  $("#modal-delete-cache").on("hidden.bs.modal", function () {
    $("#selected-cache-delete").empty();
    $("#selected-cache-input-delete").val("");
  });

  // Handle individual cache file deletion button click
  $(document).on("click", ".cache-delete-btn", function (e) {
    e.preventDefault();

    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }

    const $row = $(this).closest("tr");
    const fileNameHtml = $row.find("td:eq(2)").html();
    const jobNameHtml = $row.find("td:eq(3)").html();
    const pluginHtml = $row.find("td:eq(4)").html();
    const serviceHtml = $row.find("td:eq(5)").html();

    // Also get text content for backend submission
    const fileName = $row.find("td:eq(2)").find("a").text().trim();
    const jobName = $row.find("td:eq(3)").text().trim();
    const plugin = $row.find("td:eq(4)").text().trim();
    let service;
    const $serviceCell = $row.find("td:eq(5)");
    const $serviceLink = $serviceCell.find("a");
    if ($serviceLink.length > 0) {
      service = $serviceLink.text().trim();
    } else {
      const $serviceSpan = $serviceCell.find("span");
      if (
        $serviceSpan.length &&
        $serviceSpan.attr("data-i18n") === "scope.global"
      ) {
        service = "global"; // Normalize translated global to actual value
      } else {
        service = $serviceSpan.length
          ? $serviceSpan.text().trim()
          : $serviceCell.text().trim();
      }
    }

    const cacheFile = {
      fileName,
      jobName,
      plugin,
      service,
      fileNameHtml,
      jobNameHtml,
      pluginHtml,
      serviceHtml,
    };
    setupDeletionModal([cacheFile]);
  });
});
