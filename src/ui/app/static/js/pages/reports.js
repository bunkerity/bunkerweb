$(document).ready(function () {
  const reportsNumber = parseInt($("#reports_number").val());

  const layout = {
    topStart: {},
    bottomEnd: {},
  };

  if (reportsNumber > 10) {
    const menu = [10];
    if (reportsNumber > 25) {
      menu.push(25);
    }
    if (reportsNumber > 50) {
      menu.push(50);
    }
    if (reportsNumber > 100) {
      menu.push(100);
    }
    menu.push({ label: "All", value: -1 });
    layout.topStart.pageLength = {
      menu: menu,
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
          filename: "bw_report",
          exportOptions: {
            modifier: {
              search: "none",
            },
          },
        },
        {
          extend: "excel",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel',
          filename: "bw_report",
          exportOptions: {
            modifier: {
              search: "none",
            },
          },
        },
      ],
    },
  ];

  $(".report-date").each(function () {
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

  const reports_table = new DataTable("#reports", {
    columnDefs: [
      {
        orderable: false,
        targets: -1,
      },
      {
        visible: false,
        targets: [6, -1],
      },
      {
        targets: "_all", // Target all columns
        createdCell: function (td, cellData, rowData, row, col) {
          $(td).addClass("align-items-center"); // Apply 'text-center' class to <td>
        },
      },
    ],
    order: [[0, "desc"]],
    autoFill: false,
    responsive: true,
    layout: layout,
    language: {
      info: "Showing _START_ to _END_ of _TOTAL_ reports",
      infoEmpty: "No reports available",
      infoFiltered: "(filtered from _MAX_ total reports)",
      lengthMenu: "Display _MENU_ reports",
      zeroRecords: "No matching reports found",
      select: {
        rows: {
          _: "Selected %d reports",
          0: "No reports selected",
          1: "Selected 1 report",
        },
      },
    },
    initComplete: function (settings, json) {
      $("#reports_wrapper .btn-secondary").removeClass("btn-secondary");
      $("#reports_wrapper th").addClass("text-center");
    },
  });

  reports_table.on("mouseenter", "td", function () {
    if (reports_table.cell(this).index() === undefined) return;
    const rowIdx = reports_table.cell(this).index().row;

    reports_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));

    reports_table
      .cells()
      .nodes()
      .each(function (el) {
        if (reports_table.cell(el).index().row === rowIdx)
          el.classList.add("highlight");
      });
  });

  reports_table.on("mouseleave", "td", function () {
    reports_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));
  });
});
