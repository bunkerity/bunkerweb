$(document).ready(function () {
  var toastNum = 0;
  var actionLock = false;
  const serviceNumber = parseInt($("#services_number").val());

  const layout = {
    topStart: {},
    bottomEnd: {},
  };

  if (serviceNumber > 10) {
    layout.topStart.pageLength = {
      menu: [10, 25, 50, 100, { label: "All", value: -1 }],
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
          filename: "bw_services",
          exportOptions: {
            modifier: {
              search: "none",
            },
          },
        },
        {
          extend: "excel",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel',
          filename: "bw_services",
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
          extend: "clone_service",
        },
        {
          extend: "convert_services",
          text: '<span class="tf-icons bx bx-globe bx-18px me-2"></span>Convert to<span class="d-none d-md-inline"> online</span>',
        },
        {
          extend: "convert_services",
          text: '<span class="tf-icons bx bx-file-blank bx-18px me-2"></span>Convert to<span class="d-none d-md-inline"> draft</span>',
        },
        {
          extend: "delete_services",
          className: "text-danger",
        },
      ],
    },
    {
      extend: "create_service",
    },
  ];

  $(document).on("hidden.bs.toast", ".toast", function (event) {
    if (event.target.id.startsWith("feedback-toast")) {
      setTimeout(() => {
        $(this).remove();
      }, 100);
    }
  });

  $("#modal-delete-services").on("hidden.bs.modal", function () {
    $("#selected-services-delete").empty();
    $("#selected-services-input-delete").val("");
  });

  $("#modal-convert-services").on("hidden.bs.modal", function () {
    $("#selected-services-convert").empty();
    $("#selected-services-input-convert").val("");
  });

  const getSelectedservices = () => {
    const services = [];
    $("tr.selected").each(function () {
      services.push($(this).find("td:eq(1)").find("a").text().trim());
    });
    return services;
  };

  $.fn.dataTable.ext.buttons.create_service = {
    text: '<span class="tf-icons bx bx-plus-circle bx-18px me-2"></span>Create<span class="d-none d-md-inline"> new service</span>',
    className: "btn btn-sm btn-outline-bw-green",
    action: function (e, dt, node, config) {
      window.location.href = `${window.location.href}/new`;
    },
  };

  $.fn.dataTable.ext.buttons.clone_service = {
    text: '<span class="tf-icons bx bx-copy-alt bx-18px me-2"></span>Clone<span class="d-none d-md-inline"> service</span>',
    action: function (e, dt, node, config) {
      if (actionLock) {
        return;
      }
      actionLock = true;
      const services = getSelectedservices();
      if (services.length === 0) {
        actionLock = false;
        return;
      } else if (services.length > 1) {
        const feedbackToast = $("#feedback-toast").clone(); // Clone the feedback toast
        feedbackToast.attr("id", `feedback-toast-${toastNum++}`); // Corrected to set the ID for the failed toast
        feedbackToast.removeClass("bg-primary text-white");
        feedbackToast.addClass("bg-primary text-white");
        feedbackToast.find("span").text("Clone failed");
        feedbackToast
          .find("div.toast-body")
          .text("Only one service can be cloned at a time.");
        feedbackToast.appendTo("#feedback-toast-container"); // Ensure the toast is appended to the container
        feedbackToast.toast("show");
        actionLock = false;
        return;
      }

      window.location.href = `${window.location.href}/new?clone=${services[0]}`;
    },
  };

  $.fn.dataTable.ext.buttons.convert_services = {
    action: function (e, dt, node, config) {
      if (actionLock) {
        return;
      }
      actionLock = true;
      $(".dt-button-background").click();
      const convertionType = $(node).text().trim().split(" ")[2];

      const services = getSelectedservices();
      if (services.length === 0) {
        actionLock = false;
        return;
      }

      const filteredServices = services.filter(function (service) {
        const serviceType = $(`#type-${service.replace(/\./g, "-")}`);
        return serviceType.data("value") !== convertionType;
      });
      if (filteredServices.length === 0) {
        const feedbackToast = $("#feedback-toast").clone(); // Clone the feedback toast
        feedbackToast.attr("id", `feedback-toast-${toastNum++}`); // Corrected to set the ID for the failed toast
        feedbackToast.removeClass("bg-primary text-white");
        feedbackToast.addClass("bg-primary text-white");
        feedbackToast.find("span").text("Conversion failed");
        feedbackToast
          .find("div.toast-body")
          .text("The selected services are already in the desired state.");
        feedbackToast.appendTo("#feedback-toast-container"); // Ensure the toast is appended to the container
        feedbackToast.toast("show");
        actionLock = false;
        return;
      }

      $("#selected-services-input-convert").val(services.join(","));

      services.forEach((service) => {
        // Create the list item using template literals
        const listItem =
          $(`<li class="list-group-item d-flex justify-content-between align-items-center">
          <div class="ms-2 me-auto">
          <div class="fw-bold">${service}</div>
          </div>
          </li>`);

        // Clone the type element and append it to the list item
        const typeClone = $("#type-" + service.replace(/\./g, "-")).clone();
        listItem.append(typeClone);

        // Append the list item to the list
        $("#selected-services-convert").append(listItem);
      });

      const convert_modal = $("#modal-convert-services");
      convert_modal
        .find(".modal-title")
        .text(
          `Convert services to ${
            convertionType.charAt(0).toUpperCase() + convertionType.slice(1)
          }`,
        );
      convert_modal
        .find(".alert")
        .text(
          `Are you sure you want to convert the selected services to ${convertionType}?`,
        );
      convert_modal
        .find("button[type=submit]")
        .text(`Convert to ${convertionType}`);
      $("#convertion-type").val(convertionType);
      const modal = new bootstrap.Modal(convert_modal);
      modal.show();

      actionLock = false;
    },
  };

  $.fn.dataTable.ext.buttons.delete_services = {
    text: '<span class="tf-icons bx bx-trash bx-18px me-2"></span>Delete',
    action: function (e, dt, node, config) {
      if (actionLock) {
        return;
      }
      actionLock = true;
      $(".dt-button-background").click();

      const services = getSelectedservices();
      if (services.length === 0) {
        actionLock = false;
        return;
      }

      $("#selected-services-input-delete").val(services.join(","));

      const delete_modal = $("#modal-delete-services");
      services.forEach((service) => {
        // Create the list item using template literals
        const listItem =
          $(`<li class="list-group-item d-flex justify-content-between align-items-center">
  <div class="ms-2 me-auto">
    <div class="fw-bold">${service}</div>
  </div>
</li>`);

        // Clone the type element and append it to the list item
        const typeClone = $("#type-" + service.replace(/\./g, "-")).clone();
        listItem.append(typeClone);

        // Append the list item to the list
        $("#selected-services-delete").append(listItem);
      });

      const modal = new bootstrap.Modal(delete_modal);
      modal.show();

      actionLock = false;
    },
  };

  const services_table = new DataTable("#services", {
    columnDefs: [
      {
        orderable: false,
        render: DataTable.render.select(),
        targets: 0,
      },
      {
        targets: "_all", // Target all columns
        createdCell: function (td, cellData, rowData, row, col) {
          $(td).addClass("text-center align-items-center"); // Apply 'text-center' class to <td>
        },
      },
    ],
    order: [[5, "desc"]],
    autoFill: false,
    responsive: true,
    select: {
      style: "multi+shift",
      selector: "td:first-child",
      headerCheckbox: false,
    },
    layout: layout,
    language: {
      info: "Showing _START_ to _END_ of _TOTAL_ services",
      infoEmpty: "No services available",
      infoFiltered: "(filtered from _MAX_ total services)",
      lengthMenu: "Display _MENU_ services",
      zeroRecords: "No matching services found",
      select: {
        rows: {
          _: "Selected %d services",
          0: "No services selected",
          1: "Selected 1 service",
        },
      },
    },
    initComplete: function (settings, json) {
      $("#services_wrapper .btn-secondary").removeClass("btn-secondary");
    },
  });

  services_table.on("mouseenter", "td", function () {
    const rowIdx = services_table.cell(this).index().row;

    services_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));

    services_table
      .cells()
      .nodes()
      .each(function (el) {
        if (services_table.cell(el).index().row === rowIdx)
          el.classList.add("highlight");
      });
  });

  services_table.on("mouseleave", "td", function () {
    services_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));
  });

  // Event listener for the select-all checkbox
  $("#select-all-rows").on("change", function () {
    const isChecked = $(this).prop("checked");

    if (isChecked) {
      // Select all rows on the current page
      services_table.rows({ page: "current" }).select();
    } else {
      // Deselect all rows on the current page
      services_table.rows({ page: "current" }).deselect();
    }
  });
});
