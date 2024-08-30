$(document).ready(function () {
  $.fn.dataTable.ext.buttons.create_instance = {
    text: "Create new instance",
    className: "btn btn-sm btn-outline-primary",
    action: function (e, dt, node, config) {
      var modal = new bootstrap.Modal($("#modal-create-instance"));
      modal.show();
    },
  };

  const instances_table = new DataTable("#instances", {
    columnDefs: [{ orderable: false, targets: 7 }],
    order: [[6, "desc"]],
    autoFill: false,
    colReorder: true,
    responsive: true,
    layout: {
      topStart: {
        pageLength: {
          menu: [10, 25, 50, 100, { label: "All", value: -1 }],
        },
        buttons: [
          {
            extend: "colvis",
            columns: "th:not(:first-child):not(:last-child)",
            text: "Columns",
            className: "btn btn-sm btn-outline-primary",
            columnText: function (dt, idx, title) {
              return idx + 1 + ". " + title;
            },
          },
          {
            extend: "colvisRestore",
            text: "Reset",
            className: "btn btn-sm btn-outline-primary",
          },
          {
            extend: "collection",
            text: "Export",
            className: "btn btn-sm btn-outline-primary",
            buttons: [
              {
                extend: "copy",
                text: "Copy current page",
                exportOptions: {
                  modifier: {
                    page: "current",
                  },
                },
              },
              {
                extend: "csv",
                bom: true,
                filename: "bw_instances",
                exportOptions: {
                  modifier: {
                    search: "none",
                  },
                },
              },
              {
                extend: "excel",
                filename: "bw_instances",
                exportOptions: {
                  modifier: {
                    search: "none",
                  },
                },
              },
            ],
          },
          {
            extend: "create_instance",
          },
        ],
      },
    },
  });

  instances_table.on("mouseenter", "td", function () {
    const colIdx = instances_table.cell(this).index().column;

    instances_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));

    instances_table
      .column(colIdx)
      .nodes()
      .each((el) => el.classList.add("highlight"));
  });

  $(document).on("click", "button[data-action]", function () {
    const form = $(this).closest("form");
    const action = $(this).data("action"); // Get the action from the button
    const actionSplit = form.attr("action").split("/");
    const instanceHostname = actionSplit[actionSplit.length - 1];

    if (
      action === "delete" &&
      $(`#method-${instanceHostname}`).text() !== "ui"
    ) {
      return;
    } else if ($(`#status-${instanceHostname}`).text() !== "Up") {
      return;
    }

    form.attr("action", `${form.attr("action")}/${action}`);

    // Now, submit the form with the updated action
    form.off("submit").submit();
  });
});
