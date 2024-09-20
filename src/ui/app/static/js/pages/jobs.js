$(document).ready(function () {
  const jobNumber = parseInt($("#job_number").val());

  const layout = {
    topStart: {},
    bottomEnd: {},
  };

  if (jobNumber > 10) {
    layout.topStart.pageLength = {
      menu: [10, 25, 50, 100, { label: "All", value: -1 }],
    };
    layout.bottomEnd.paging = true;
  }

  layout.topStart.buttons = [
    {
      extend: "colvis",
      columns: "th:not(:first-child)",
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
          filename: "bw_jobs",
          exportOptions: {
            modifier: {
              search: "none",
            },
          },
        },
        {
          extend: "excel",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel',
          filename: "bw_jobs",
          exportOptions: {
            modifier: {
              search: "none",
            },
          },
        },
      ],
    },
  ];

  $(".history-start-date, .history-end-date").each(function () {
    const isoDateStr = $(this).text().trim();

    // Parse the ISO format date string
    const date = new Date(isoDateStr);

    // Check if the date is valid
    if (!isNaN(date)) {
      // Convert to local date and time string
      const localDateStr = date.toLocaleString();

      // Update the text content with the local date string
      $(this).text(localDateStr);
    } else {
      // Handle invalid date
      console.error(`Invalid date string: ${isoDateStr}`);
      $(this).text("Invalid date");
    }
  });

  const jobs_table = new DataTable("#jobs", {
    columnDefs: [
      {
        orderable: false,
        targets: -1,
      },
      {
        targets: "_all", // Target all columns
        createdCell: function (td, cellData, rowData, row, col) {
          $(td).addClass("align-items-center"); // Apply 'text-center' class to <td>
        },
      },
    ],
    order: [[1, "asc"]],
    autoFill: false,
    responsive: true,
    layout: layout,
    language: {
      info: "Showing _START_ to _END_ of _TOTAL_ jobs",
      infoEmpty: "No jobs available",
      infoFiltered: "(filtered from _MAX_ total jobs)",
      lengthMenu: "Display _MENU_ jobs",
      zeroRecords: "No matching jobs found",
    },
    initComplete: function (settings, json) {
      $("#jobs_wrapper .btn-secondary").removeClass("btn-secondary");
      $("#jobs_wrapper th").addClass("text-center");
    },
  });

  jobs_table.on("mouseenter", "td", function () {
    if (jobs_table.cell(this).index() === undefined) return;
    const rowIdx = jobs_table.cell(this).index().row;

    jobs_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));

    jobs_table
      .cells()
      .nodes()
      .each(function (el) {
        if (jobs_table.cell(el).index().row === rowIdx)
          el.classList.add("highlight");
      });
  });

  jobs_table.on("mouseleave", "td", function () {
    jobs_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));
  });

  $(".show-history").on("click", function () {
    const historyModal = $("#modal-job-history");
    const job = $(this).data("job");
    const plugin = $(this).data("plugin");

    historyModal.find(".modal-title").text(`Job ${job} History`);
    const history = $(`#job-${job}-${plugin}-history`).clone();
    history.removeClass("visually-hidden");
    historyModal.find(".modal-body").html(history);

    const modal = new bootstrap.Modal(historyModal);
    modal.show();
  });
});
