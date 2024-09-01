$(document).ready(function () {
  const getSelectedInstances = (action) => {
    const instances = [];
    $("tr.selected").each(function () {
      instances.push($(this).find("td:first").text());
    });
    return instances;
  };
  var toastNum = 0;
  var actionLock = false;

  $.fn.dataTable.ext.buttons.create_instance = {
    text: "Create new instance",
    className: "btn btn-sm btn-outline-primary",
    action: function (e, dt, node, config) {
      const modal = new bootstrap.Modal($("#modal-create-instance"));
      modal.show();

      $("#modal-create-instance").on("shown.bs.modal", function () {
        $(this).find("#hostname").focus();
      });
    },
  };

  $.fn.dataTable.ext.buttons.ping_instances = {
    text: '<span class="tf-icons bx bx-bell bx-18px me-md-2"></span><span class="d-none d-md-inline">Ping</span>',
    className: "btn btn-sm btn-outline-primary",
    action: function (e, dt, node, config) {
      if (actionLock) {
        return;
      }
      actionLock = true;

      const instances = getSelectedInstances("ping");
      if (instances.length === 0) {
        actionLock = false;
        return;
      }

      setTimeout(() => {
        if (actionLock) {
          $("#loadingModal").modal("show");
        }
      }, 500);

      // Create a FormData object
      const formData = new FormData();
      formData.append("csrf_token", $("#csrf_token").val()); // Add the CSRF token
      formData.append("instances", instances.join(",")); // Add the instances

      // Send the form data using $.ajax
      $.ajax({
        url: `${window.location.pathname}/ping`,
        type: "POST",
        data: formData,
        processData: false,
        contentType: false,
        success: function (data) {
          data.failed.forEach((instance) => {
            var feedbackToastFailed = $("#feedback-toast").clone(); // Clone the feedback toast
            feedbackToastFailed.attr("id", `feedback-toast-${toastNum++}`); // Corrected to set the ID for the failed toast
            feedbackToastFailed.removeClass("bg-primary text-white");
            feedbackToastFailed.addClass("bg-danger text-white");
            feedbackToastFailed.find("span").text("Ping failed");
            feedbackToastFailed.find("div.toast-body").text(instance.message);
            feedbackToastFailed.appendTo("#feedback-toast-container"); // Ensure the toast is appended to the container
            feedbackToastFailed.toast("show");
          });

          if (data.succeed.length > 0) {
            var feedbackToastSucceed = $("#feedback-toast").clone(); // Clone the feedback toast
            feedbackToastSucceed.attr("id", `feedback-toast-${toastNum++}`);
            feedbackToastSucceed.addClass("bg-primary text-white");
            feedbackToastSucceed.find("span").text("Ping successful");
            feedbackToastSucceed
              .find("div.toast-body")
              .text(`Instances: ${data.succeed.join(", ")}`);
            feedbackToastSucceed.appendTo("#feedback-toast-container");
            feedbackToastSucceed.toast("show");
          }
        },
        error: function (xhr, status, error) {
          console.error("AJAX request failed:", status, error);
          alert("An error occurred while pinging the instances.");
        },
        complete: function () {
          actionLock = false;
          $("#loadingModal").modal("hide");
        },
      });
    },
  };

  $.fn.dataTable.ext.buttons.exec_form = {
    action: function (e, dt, node, config) {
      if (actionLock) {
        return;
      }
      actionLock = true;

      const instances = getSelectedInstances("ping");
      if (instances.length === 0) {
        actionLock = false;
        return;
      }

      const bxIcon = node.find("span.bx").attr("class").split(" ")[2];
      if (bxIcon === "bx-refresh") {
        var action = "reload";
      } else if (bxIcon === "bx-stop") {
        var action = "stop";
      } else {
        actionLock = false;
        return;
      }

      // Create a form element using jQuery and set its attributes
      const $form = $("<form>", {
        method: "POST",
        action: `${window.location.pathname}/${action}`,
        class: "visually-hidden",
      });

      // Add CSRF token and instances as hidden inputs
      $form.append(
        $("<input>", {
          type: "hidden",
          name: "csrf_token",
          value: $("#csrf_token").val(),
        }),
      );
      $form.append(
        $("<input>", {
          type: "hidden",
          name: "instances",
          value: instances.join(","),
        }),
      );

      // Append the form to the body and submit it
      $form.appendTo("body").submit();
    },
  };

  $.fn.dataTable.ext.buttons.delete_instances = {
    text: '<span class="tf-icons bx bx-trash bx-18px me-md-2"></span><span class="d-none d-md-inline">Delete</span>',
    className: "btn btn-sm btn-outline-danger",
    action: function (e, dt, node, config) {
      if (actionLock) {
        return;
      }
      actionLock = true;

      const instances = getSelectedInstances("ping");
      if (instances.length === 0) {
        actionLock = false;
        return;
      }

      $("#selected-instances-input").val(instances.join(","));

      const delete_modal = $("#modal-delete-instances");
      instances.forEach((instance) => {
        // Create the list item using template literals
        const listItem =
          $(`<li class="list-group-item d-flex justify-content-between align-items-center">
  <div class="ms-2 me-auto">
    <div class="fw-bold">${instance}</div>
  </div>
</li>`);

        // Clone the status element and append it to the list item
        const statusClone = $("#status-" + instance).clone();
        listItem.append(statusClone);

        // Append the list item to the list
        $("#selected-instances").append(listItem);
      });

      const modal = new bootstrap.Modal(delete_modal);
      modal.show();

      actionLock = false;
    },
  };

  const instances_table = new DataTable("#instances", {
    columnDefs: [
      {
        targets: "_all", // Target all columns
        createdCell: function (td, cellData, rowData, row, col) {
          $(td).addClass("text-center"); // Apply 'text-center' class to <td>
        },
      },
    ],
    order: [[6, "desc"]],
    autoFill: false,
    colReorder: true,
    responsive: true,
    select: {
      style: "multi+shift",
    },
    layout: {
      topStart: {
        pageLength: {
          menu: [10, 25, 50, 100, { label: "All", value: -1 }],
        },
        buttons: [
          {
            extend: "colvis",
            columns: "th:not(:first-child)",
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
      bottomEnd: {
        buttons: [
          {
            extend: "ping_instances",
          },
          {
            extend: "exec_form",
            text: '<span class="tf-icons bx bx-refresh bx-18px me-md-2"></span><span class="d-none d-md-inline">Reload</span>',
            className: "btn btn-sm btn-outline-primary",
          },
          {
            extend: "exec_form",
            text: '<span class="tf-icons bx bx-stop bx-18px me-md-2"></span><span class="d-none d-md-inline">Stop</span>',
            className: "btn btn-sm btn-outline-primary",
          },
          {
            extend: "delete_instances",
          },
        ],
        paging: true,
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

  $(document).on("hidden.bs.toast", ".toast", function (event) {
    if (event.target.id.startsWith("feedback-toast")) {
      setTimeout(() => {
        $(this).remove();
      }, 100);
    }
  });

  $("#modal-delete-instances").on("hidden.bs.modal", function () {
    $("#selected-instances").empty();
    $("#selected-instances-input").val("");
  });
});
