$(document).ready(function () {
  var toastNum = 0;
  var actionLock = false;
  const instanceNumber = parseInt($("#instances_number").val());
  const isReadOnly = $("#is-read-only").val().trim() === "True";

  const pingInstances = (instances) => {
    setTimeout(() => {
      if (actionLock) {
        $(".dt-button-background").click();
        $("#loadingModal").modal("show");
        setTimeout(() => {
          $("#loadingModal").modal("hide");
        }, 5300);
      }
    }, 500);

    // Create a FormData object
    const formData = new FormData();
    formData.append("csrf_token", $("#csrf_token").val()); // Add the CSRF token // TODO: find a way to ignore CSRF token
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
  };

  const setupDeletionModal = (instances) => {
    $("#selected-instances-input").val(instances.join(","));

    const list = $(
      `<ul class="list-group list-group-horizontal d-flex w-100">
        <li class="list-group-item align-items-center text-center bg-secondary text-white" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold">Hostname</div>
          </div>
        </li>
        <li class="list-group-item align-items-center text-center bg-secondary text-white" style="flex: 1 0;">
          <div class="fw-bold">Health</div>
        </li>
        </ul>`,
    );
    $("#selected-instances").append(list);

    const delete_modal = $("#modal-delete-instances");
    instances.forEach((instance) => {
      const list = $(
        `<ul class="list-group list-group-horizontal d-flex w-100"></ul>`,
      );

      // Create the list item using template literals
      const listItem =
        $(`<li class="list-group-item align-items-center" style="flex: 1 0;">
  <div class="ms-2 me-auto">
    <div class="fw-bold">${instance}</div>
  </div>
</li>`);
      list.append(listItem);

      // Clone the status element and append it to the list item
      const statusClone = $("#status-" + instance).clone();
      const statusListItem = $(
        `<li class="list-group-item d-flex align-items-center justify-content-center" style="flex: 1 0;"></li>`,
      );
      statusListItem.append(statusClone.removeClass("highlight"));
      list.append(statusListItem);

      // Append the list item to the list
      $("#selected-instances").append(list);
    });

    const modal = new bootstrap.Modal(delete_modal);
    modal.show();
  };

  const execForm = (instances, action) => {
    // Create a form element using jQuery and set its attributes
    const form = $("<form>", {
      method: "POST",
      action: `${window.location.pathname}/${action}`,
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

  const layout = {
    topStart: {},
    bottomEnd: {},
  };

  if (instanceNumber > 10) {
    const menu = [10];
    if (instanceNumber > 25) {
      menu.push(25);
    }
    if (instanceNumber > 50) {
      menu.push(50);
    }
    if (instanceNumber > 100) {
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
      columns: "th:not(:first-child):not(:nth-child(2))",
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
          filename: "bw_instances",
          exportOptions: {
            modifier: {
              search: "none",
            },
          },
        },
        {
          extend: "excel",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel',
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
      extend: "collection",
      text: '<span class="tf-icons bx bx-play bx-18px me-2"></span>Actions',
      className: "btn btn-sm btn-outline-primary",
      buttons: [
        {
          extend: "ping_instances",
        },
        {
          extend: "exec_form",
          text: '<span class="tf-icons bx bx-refresh bx-18px me-2"></span>Reload',
        },
        {
          extend: "exec_form",
          text: '<span class="tf-icons bx bx-stop bx-18px me-2"></span>Stop',
        },
        {
          extend: "delete_instances",
          className: "text-danger",
        },
      ],
    },
    {
      extend: "create_instance",
    },
  ];

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

  const getSelectedInstances = () => {
    const instances = [];
    $("tr.selected").each(function () {
      instances.push($(this).find("td:eq(1)").text());
    });
    return instances;
  };

  $.fn.dataTable.ext.buttons.create_instance = {
    text: '<span class="tf-icons bx bx-plus-circle bx-18px me-2"></span>Create<span class="d-none d-md-inline"> new instance</span>',
    className: `btn btn-sm btn-outline-bw-green${
      isReadOnly ? " disabled" : ""
    }`,
    action: function (e, dt, node, config) {
      if (isReadOnly) {
        alert("This action is not allowed in read-only mode.");
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
    text: '<span class="tf-icons bx bx-bell bx-18px me-2"></span>Ping',
    action: function (e, dt, node, config) {
      if (actionLock) {
        return;
      }
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
      if (actionLock) {
        return;
      }
      actionLock = true;

      const instances = getSelectedInstances();
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

      execForm(instances, action);
    },
  };

  $.fn.dataTable.ext.buttons.delete_instances = {
    text: '<span class="tf-icons bx bx-trash bx-18px me-2"></span>Delete',
    action: function (e, dt, node, config) {
      if (isReadOnly) {
        alert("This action is not allowed in read-only mode.");
        return;
      }
      if (actionLock) {
        return;
      }
      actionLock = true;
      $(".dt-button-background").click();

      const instances = getSelectedInstances();
      if (instances.length === 0) {
        actionLock = false;
        return;
      }

      setupDeletionModal(instances);

      actionLock = false;
    },
  };

  $(".instance-creation-date, .instance-last-seen-date").each(function () {
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

  const instances_table = new DataTable("#instances", {
    columnDefs: [
      {
        orderable: false,
        render: DataTable.render.select(),
        targets: 0,
      },
      {
        orderable: false,
        targets: -1,
      },
      {
        visible: false,
        targets: [2, 3],
      },
      {
        targets: "_all", // Target all columns
        createdCell: function (td, cellData, rowData, row, col) {
          $(td).addClass("align-items-center"); // Apply 'text-center' class to <td>
        },
      },
    ],
    order: [[7, "desc"]],
    autoFill: false,
    responsive: true,
    select: {
      style: "multi+shift",
      selector: "td:first-child",
      headerCheckbox: false,
    },
    layout: layout,
    language: {
      info: "Showing _START_ to _END_ of _TOTAL_ instances",
      infoEmpty: "No instances available",
      infoFiltered: "(filtered from _MAX_ total instances)",
      lengthMenu: "Display _MENU_ instances",
      zeroRecords: "No matching instances found",
      select: {
        rows: {
          _: "Selected %d instances",
          0: "No instances selected",
          1: "Selected 1 instance",
        },
      },
    },
    initComplete: function (settings, json) {
      $("#instances_wrapper .btn-secondary").removeClass("btn-secondary");
      $("#instances_wrapper th").addClass("text-center");
      if (isReadOnly)
        $("#instances_wrapper .dt-buttons")
          .attr(
            "data-bs-original-title",
            "The database is in readonly, therefore you cannot create new instances.",
          )
          .attr("data-bs-placement", "right")
          .tooltip();
    },
  });

  instances_table.on("mouseenter", "td", function () {
    if (instances_table.cell(this).index() === undefined) return;
    const rowIdx = instances_table.cell(this).index().row;

    instances_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));

    instances_table
      .cells()
      .nodes()
      .each(function (el) {
        if (instances_table.cell(el).index().row === rowIdx)
          el.classList.add("highlight");
      });
  });

  instances_table.on("mouseleave", "td", function () {
    instances_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));
  });

  // Event listener for the select-all checkbox
  $("#select-all-rows").on("change", function () {
    const isChecked = $(this).prop("checked");

    if (isChecked) {
      // Select all rows on the current page
      instances_table.rows({ page: "current" }).select();
    } else {
      // Deselect all rows on the current page
      instances_table.rows({ page: "current" }).deselect();
    }
  });

  $(".ping-instance").on("click", function () {
    if (actionLock) {
      return;
    }
    actionLock = true;

    const instance = $(this).data("instance");
    pingInstances([instance]);
  });

  $(".reload-instance, .stop-instance").on("click", function () {
    const instance = $(this).data("instance");
    const action = $(this).hasClass("reload-instance") ? "reload" : "stop";
    execForm([instance], action);
  });

  $(".delete-instance").on("click", function () {
    if (isReadOnly) {
      alert("This action is not allowed in read-only mode.");
      return;
    }
    const instance = $(this).data("instance");
    setupDeletionModal([instance]);
  });
});
