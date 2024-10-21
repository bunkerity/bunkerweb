$(document).ready(function () {
  const cacheNumber = parseInt($("#cache_number").val());
  const services = $("#services").val().trim().split(" ");
  const cacheServiceSelection = $("#cache_service_selection").val().trim();
  const cachePluginSelection = $("#cache_plugin_selection").val().trim();
  const cacheJobNameSelection = $("#cache_job_name_selection").val().trim();

  const servicesSearchPanesOptions = [
    {
      label: "global",
      value: function (rowData) {
        return $(rowData[3]).text().trim() === "global";
      },
    },
  ];

  services.forEach((service) => {
    servicesSearchPanesOptions.push({
      label: service,
      value: function (rowData) {
        return $(rowData[3]).text().trim() === service;
      },
    });
  });

  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [1, 2, 3, 4],
      },
    },
    topStart: {},
    topEnd: {
      buttons: [
        {
          extend: "toggle_filters",
          className: "btn btn-sm btn-outline-primary toggle-filters",
        },
      ],
      search: true,
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
      columns: "th:not(:first-child):not(:last-child)",
      text: '<span class="tf-icons bx bx-columns bx-18px me-2"></span>Columns',
      className: "btn btn-sm btn-outline-primary",
      columnText: function (dt, idx, title) {
        return idx + 1 + ". " + title;
      },
    },
    {
      extend: "colvisRestore",
      text: '<span class="tf-icons bx bx-reset bx-18px me-2"></span>Reset<span class="d-none d-md-inline"> columns</span>',
      className: "btn btn-sm btn-outline-primary",
    },
    {
      extend: "collection",
      text: '<span class="tf-icons bx bx-export bx-18px me-2"></span>Export',
      className: "btn btn-sm btn-outline-primary",
      buttons: [
        {
          extend: "copy",
          text: '<span class="tf-icons bx bx-copy bx-18px me-2"></span>Copy visible',
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
            columns: ":not(:last-child)",
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
            columns: ":not(:last-child)",
          },
        },
      ],
    },
  ];

  $.fn.dataTable.ext.buttons.toggle_filters = {
    text: '<span class="tf-icons bx bx-filter bx-18px me-2"></span><span id="show-filters">Show</span><span id="hide-filters" class="d-none">Hide</span><span class="d-none d-md-inline"> filters</span>',
    action: function (e, dt, node, config) {
      cache_table.searchPanes.container().slideToggle(); // Smoothly hide or show the container
      $("#show-filters").toggleClass("d-none"); // Toggle the visibility of the 'Show' span
      $("#hide-filters").toggleClass("d-none"); // Toggle the visibility of the 'Hide' span
    },
  };

  $(".cache-last-update-date").each(function () {
    const isoDateStr = $(this).text().trim();

    // Parse the ISO format date string
    const date = new Date(isoDateStr);

    // Check if the date is valid
    if (!isNaN(date)) {
      // Convert to local date and time string
      const localDateStr = date.toLocaleString();

      // Update the text content with the local date string
      $(this).text(localDateStr);
    }
  });

  const cache_table = new DataTable("#cache", {
    columnDefs: [
      {
        orderable: false,
        targets: -1,
      },
      {
        visible: false,
        targets: 5,
      },
      {
        searchPanes: {
          show: true,
          combiner: "or",
        },
        targets: [1, 2],
      },
      {
        searchPanes: {
          show: true,
          combiner: "or",
          options: servicesSearchPanesOptions,
        },
        targets: 3,
      },
      {
        searchPanes: {
          show: true,
          options: [
            {
              label: "Last 24 hours",
              value: function (rowData, rowIdx) {
                const date = new Date(rowData[4]);
                const now = new Date();
                return now - date < 24 * 60 * 60 * 1000;
              },
            },
            {
              label: "Last 7 days",
              value: function (rowData, rowIdx) {
                const date = new Date(rowData[4]);
                const now = new Date();
                return now - date < 7 * 24 * 60 * 60 * 1000;
              },
            },
            {
              label: "Last 30 days",
              value: function (rowData, rowIdx) {
                const date = new Date(rowData[4]);
                const now = new Date();
                return now - date < 30 * 24 * 60 * 60 * 1000;
              },
            },
          ],
          combiner: "or",
          orderable: false,
        },
        targets: 4,
      },
    ],
    order: [[2, "asc"]],
    autoFill: false,
    responsive: true,
    layout: layout,
    language: {
      info: "Showing _START_ to _END_ of _TOTAL_ cache files",
      infoEmpty: "No cache files available",
      infoFiltered: "(filtered from _MAX_ total cache files)",
      lengthMenu: "Display _MENU_ cache files",
      zeroRecords: "No matching cache files found",
    },
    initComplete: function (settings, json) {
      $("#cache_wrapper .btn-secondary").removeClass("btn-secondary");
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

  if (!cacheJobNameSelection && !cachePluginSelection && !cacheServiceSelection)
    cache_table.searchPanes.container().hide();

  $("#cache").removeClass("d-none");
  $("#cache-waiting").addClass("visually-hidden");

  cache_table.on("mouseenter", "td", function () {
    if (cache_table.cell(this).index() === undefined) return;
    const rowIdx = cache_table.cell(this).index().row;

    cache_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));

    cache_table
      .cells()
      .nodes()
      .each(function (el) {
        if (cache_table.cell(el).index().row === rowIdx)
          el.classList.add("highlight");
      });
  });

  cache_table.on("mouseleave", "td", function () {
    cache_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));
  });
});
