$(document).ready(function () {
  const cacheNumber = parseInt($("#cache_number").val());

  const layout = {
    topStart: {},
    bottomEnd: {},
  };

  if (cacheNumber > 10) {
    layout.topStart.pageLength = {
      menu: [10, 25, 50, 100, { label: "All", value: -1 }],
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
          text: '<span class="tf-icons bx bx-copy bx-18px me-2"></span>Copy current page',
          exportOptions: {
            modifier: {
              page: "current",
            },
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
          },
        },
      ],
    },
  ];

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
        targets: "_all", // Target all columns
        createdCell: function (td, cellData, rowData, row, col) {
          $(td).addClass("text-center align-items-center"); // Apply 'text-center' class to <td>
        },
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
      select: {
        rows: {
          _: "Selected %d cache files",
          0: "No cache files selected",
          1: "Selected 1 cache file",
        },
      },
    },
    initComplete: function (settings, json) {
      $("#cache_wrapper .btn-secondary").removeClass("btn-secondary");
    },
  });

  cache_table.on("mouseenter", "td", function () {
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
