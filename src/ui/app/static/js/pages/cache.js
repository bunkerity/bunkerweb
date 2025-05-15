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

  const servicesSearchPanesOptions = [
    {
      label: "global",
      value: function (rowData) {
        return $(rowData[4]).text().trim() === "global";
      },
    },
  ];

  services.forEach((service) => {
    servicesSearchPanesOptions.push({
      label: service,
      value: function (rowData) {
        return $(rowData[4]).text().trim() === service;
      },
    });
  });

  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [2, 3, 4, 5],
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
  ];

  const cache_table = initializeDataTable({
    tableSelector: "#cache",
    tableName: "cache",
    columnVisibilityCondition: (column) => 2 < column && column < 7,
    dataTableOptions: {
      columnDefs: [
        {
          orderable: false,
          className: "dtr-control",
          targets: 0,
        },
        {
          orderable: false,
          targets: -1,
        },
        {
          visible: false,
          targets: 6,
        },
        {
          targets: 5,
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
          targets: 2,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.plugin", "Plugin"),
            combiner: "or",
          },
          targets: 3,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.service", "Service"),
            combiner: "or",
            options: servicesSearchPanesOptions,
          },
          targets: 4,
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
                  new Date() - new Date(rowData[5]) < 86400000,
              },
              {
                label: `<span data-i18n="searchpane.last_7d">${t(
                  "searchpane.last_7d",
                  "Last 7 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[5]) < 604800000,
              },
              {
                label: `<span data-i18n="searchpane.last_30d">${t(
                  "searchpane.last_30d",
                  "Last 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[5]) < 2592000000,
              },
              {
                label: `<span data-i18n="searchpane.older_30d">${t(
                  "searchpane.older_30d",
                  "More than 30 days",
                )}</span>`,
                value: (rowData) =>
                  new Date() - new Date(rowData[5]) >= 2592000000,
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 5,
        },
      ],
      order: [[3, "asc"]],
      autoFill: false,
      responsive: true,
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
    $("#show-filters").toggleClass("d-none"); // Toggle the visibility of the 'Show' span
    $("#hide-filters").toggleClass("d-none"); // Toggle the visibility of the 'Hide' span
  }
});
