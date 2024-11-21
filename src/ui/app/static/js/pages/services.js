$(function () {
  let toastNum = 0;
  let actionLock = false;
  const serviceNumber = parseInt($("#services_number").val(), 10) || 0;
  const isReadOnly = $("#is-read-only").val().trim() === "True";

  const setupModal = (services, modal) => {
    const headerList = $(`
      <ul class="list-group list-group-horizontal w-100">
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold">Service name</div>
          </div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="fw-bold">Type</div>
        </li>
      </ul>
    `);
    modal.append(headerList);

    services.forEach((service) => {
      const sanitizedService = service.replace(/\./g, "-");
      const serviceList = $(
        '<ul class="list-group list-group-horizontal w-100"></ul>',
      );

      const listItem = $(`
        <li class="list-group-item" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold">${service}</div>
          </div>
        </li>
      `);
      serviceList.append(listItem);

      const typeClone = $(`#type-${sanitizedService}`)
        .clone()
        .removeClass("highlight");
      const typeListItem = $(`
        <li class="list-group-item" style="flex: 1 0;"></li>
      `);
      typeListItem.append(typeClone);
      serviceList.append(typeListItem);

      modal.append(serviceList);
    });
  };

  const setupConversionModal = (services, conversionType = "draft") => {
    $("#selected-services-input-convert").val(services.join(","));
    setupModal(services, $("#selected-services-convert"));

    const convertModal = $("#modal-convert-services");
    convertModal
      .find(".alert")
      .text(
        `Are you sure you want to convert the selected service${
          services.length > 1 ? "s" : ""
        } to ${conversionType}?`,
      );
    convertModal
      .find("button[type=submit]")
      .text(`Convert to ${conversionType}`);
    $("#convertion-type").val(conversionType);

    const modalInstance = new bootstrap.Modal(convertModal);
    modalInstance.show();
  };

  const setupDeletionModal = (services) => {
    $("#selected-services-input-delete").val(services.join(","));
    setupModal(services, $("#selected-services-delete"));

    const deleteModal = $("#modal-delete-services");
    deleteModal
      .find(".alert")
      .text(
        `Are you sure you want to delete the selected service${
          services.length > 1 ? "s" : ""
        }?`,
      );
    const modalInstance = new bootstrap.Modal(deleteModal);
    modalInstance.show();
  };

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

  if (serviceNumber > 10) {
    const menu = [10];
    [25, 50, 100].forEach((num) => {
      if (serviceNumber > num) menu.push(num);
    });
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
      extend: "create_service",
    },
    {
      extend: "colvis",
      columns: "th:not(:nth-child(-n+3)):not(:last-child)",
      text: '<span class="tf-icons bx bx-columns bx-18px me-md-2"></span><span class="d-none d-md-inline">Columns</span>',
      className: "btn btn-sm btn-outline-primary rounded-start",
      columnText: (dt, idx, title) => `${idx + 1}. ${title}`,
    },
    {
      extend: "colvisRestore",
      text: '<span class="tf-icons bx bx-reset bx-18px me-2"></span>Reset columns',
      className: "btn btn-sm btn-outline-primary d-none d-md-inline",
    },
    {
      extend: "collection",
      text: '<span class="tf-icons bx bx-export bx-18px me-md-2"></span><span class="d-none d-md-inline">Export</span>',
      className: "btn btn-sm btn-outline-primary",
      buttons: [
        {
          extend: "copy",
          text: '<span class="tf-icons bx bx-copy bx-18px me-2"></span>Copy visible',
          exportOptions: {
            columns: ":visible:not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "csv",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV',
          bom: true,
          filename: "bw_services",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel',
          filename: "bw_services",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
      ],
    },
    {
      extend: "collection",
      text: '<span class="tf-icons bx bx-play bx-18px me-md-2"></span><span class="d-none d-md-inline">Actions</span>',
      className: "btn btn-sm btn-outline-primary action-button disabled",
      buttons: [
        {
          extend: "convert_services",
          text: '<span class="tf-icons bx bx-globe bx-18px me-2"></span>Convert to<span class="d-none d-md-inline"> online</span>',
        },
        {
          extend: "convert_services",
          text: '<span class="tf-icons bx bx-file-blank bx-18px me-2"></span>Convert to<span class="d-none d-md-inline"> draft</span>',
        },
        {
          extend: "export_services",
          text: '<span class="tf-icons bx bx-export bx-18px me-2"></span>Export',
        },
        {
          extend: "delete_services",
          className: "text-danger",
        },
      ],
    },
  ];

  $(document).on("hidden.bs.toast", ".toast", function (event) {
    if (event.target.id.startsWith("feedback-toast")) {
      setTimeout(() => {
        $(this).remove();
      }, 100);
    }
  });

  $("#modal-delete-services, #modal-convert-services").on(
    "hidden.bs.modal",
    function () {
      $(this)
        .find("#selected-services-convert, #selected-services-delete")
        .empty();
      $(this)
        .find(
          "#selected-services-input-convert, #selected-services-input-delete",
        )
        .val("");
    },
  );

  const getSelectedServices = () =>
    $("tr.selected")
      .map(function () {
        return $(this).find("td:eq(2) a").text().trim();
      })
      .get();

  $.fn.dataTable.ext.buttons.toggle_filters = {
    text: '<span class="tf-icons bx bx-filter bx-18px me-2"></span><span id="show-filters">Show</span><span id="hide-filters" class="d-none">Hide</span><span class="d-none d-md-inline"> filters</span>',
    action: function (e, dt, node, config) {
      services_table.searchPanes.container().slideToggle(); // Smoothly hide or show the container
      $("#show-filters").toggleClass("d-none"); // Toggle the visibility of the 'Show' span
      $("#hide-filters").toggleClass("d-none"); // Toggle the visibility of the 'Hide' span
    },
  };

  $.fn.dataTable.ext.buttons.create_service = {
    text: '<span class="tf-icons bx bx-plus"></span><span class="d-none d-md-inline">&nbsp;Create new service</span>',
    className: `btn btn-sm rounded me-4 btn-bw-green${
      isReadOnly ? " disabled" : ""
    }`,
    action: function () {
      if (isReadOnly) {
        alert("This action is not allowed in read-only mode.");
        return;
      }
      window.location.href = `${window.location.href}/new`;
    },
  };

  $.fn.dataTable.ext.buttons.convert_services = {
    action: function (e, dt, node) {
      if (isReadOnly) {
        alert("This action is not allowed in read-only mode.");
        return;
      }
      if (actionLock) return;
      actionLock = true;
      $(".dt-button-background").click();

      const conversionType = $(node).text().trim().split(" ")[2];
      const services = getSelectedServices();
      if (services.length === 0) {
        actionLock = false;
        return;
      }

      const filteredServices = services.filter((service) => {
        const serviceType = $(`#type-${service.replace(/\./g, "-")}`).data(
          "value",
        );
        return serviceType !== conversionType;
      });

      if (filteredServices.length === 0) {
        const feedbackToast = $("#feedback-toast")
          .clone()
          .attr("id", `feedback-toast-${toastNum++}`)
          .removeClass("d-none");
        feedbackToast.find("span").text("Conversion failed");
        feedbackToast
          .find("div.toast-body")
          .text("The selected services are already in the desired state.");
        feedbackToast.appendTo("#feedback-toast-container").toast("show");
        actionLock = false;
        return;
      }

      setupConversionModal(filteredServices, conversionType);
      actionLock = false;
    },
  };

  $.fn.dataTable.ext.buttons.export_services = {
    action: function () {
      if (actionLock) return;
      actionLock = true;
      $(".dt-button-background").click();

      const services = getSelectedServices();
      if (services.length === 0) {
        actionLock = false;
        return;
      }

      const baseUrl = window.location.href;
      const exportUrl = `${baseUrl}/export?services=${services.join(",")}`;
      window.open(exportUrl, "_blank");
      actionLock = false;
    },
  };

  $.fn.dataTable.ext.buttons.delete_services = {
    text: '<span class="tf-icons bx bx-trash bx-18px me-2"></span>Delete',
    action: function () {
      if (isReadOnly) {
        alert("This action is not allowed in read-only mode.");
        return;
      }
      if (actionLock) return;
      actionLock = true;
      $(".dt-button-background").click();

      const services = getSelectedServices();
      if (services.length === 0) {
        actionLock = false;
        return;
      }

      setupDeletionModal(services);
      actionLock = false;
    },
  };

  const services_table = new DataTable("#services", {
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
      { orderable: false, targets: -1 },
      {
        targets: [5, 6],
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
          options: [
            {
              label: '<i class="bx bx-xs bx-globe"></i>&nbsp;Online',
              value: (rowData) => rowData[3].includes("Online"),
            },
            {
              label: '<i class="bx bx-xs bx-file-blank"></i>&nbsp;Draft',
              value: (rowData) => rowData[3].includes("Draft"),
            },
          ],
          combiner: "or",
          orderable: false,
        },
        targets: 3,
      },
      {
        searchPanes: {
          show: true,
          combiner: "or",
          orderable: false,
        },
        targets: 4,
      },
      {
        searchPanes: {
          show: true,
          options: [
            {
              label: "Last 24 hours",
              value: (rowData) => new Date() - new Date(rowData[5]) < 86400000,
            },
            {
              label: "Last 7 days",
              value: (rowData) => new Date() - new Date(rowData[5]) < 604800000,
            },
            {
              label: "Last 30 days",
              value: (rowData) =>
                new Date() - new Date(rowData[5]) < 2592000000,
            },
          ],
          combiner: "or",
          orderable: false,
        },
        targets: 5,
      },
      {
        searchPanes: {
          show: true,
          options: [
            {
              label: "Last 24 hours",
              value: (rowData) => new Date() - new Date(rowData[6]) < 86400000,
            },
            {
              label: "Last 7 days",
              value: (rowData) => new Date() - new Date(rowData[6]) < 604800000,
            },
            {
              label: "Last 30 days",
              value: (rowData) =>
                new Date() - new Date(rowData[6]) < 2592000000,
            },
          ],
          combiner: "or",
          orderable: false,
        },
        targets: 6,
      },
    ],
    order: [[2, "asc"]],
    autoFill: false,
    responsive: true,
    select: {
      style: "multi+shift",
      selector: "td:nth-child(2)",
      headerCheckbox: true,
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
      searchPanes: {
        collapse: {
          0: '<span class="tf-icons bx bx-search bx-18px me-2"></span>Filters',
          _: '<span class="tf-icons bx bx-search bx-18px me-2"></span>Filters (%d)',
        },
      },
    },
    initComplete: function () {
      const $wrapper = $("#services_wrapper");
      $wrapper.find(".btn-secondary").removeClass("btn-secondary");
      if (isReadOnly) {
        $wrapper
          .find(".dt-buttons")
          .attr(
            "data-bs-original-title",
            "The database is in read-only mode; you cannot create new services.",
          )
          .attr("data-bs-placement", "right")
          .tooltip();
      }
    },
  });

  services_table.searchPanes.container().hide();

  $(".action-button")
    .parent()
    .attr(
      "data-bs-original-title",
      "Please select one or more rows to perform an action.",
    )
    .attr("data-bs-placement", "top")
    .tooltip();

  $("#services").removeClass("d-none");
  $("#services-waiting").addClass("visually-hidden");

  const defaultColsVisibility = JSON.parse(
    $("#columns_preferences_defaults").val().trim(),
  );

  var columnVisibility = localStorage.getItem("bw-services-columns");
  if (columnVisibility === null) {
    columnVisibility = JSON.parse($("#columns_preferences").val().trim());
  } else {
    columnVisibility = JSON.parse(columnVisibility);
  }

  Object.entries(columnVisibility).forEach(([key, value]) => {
    services_table.column(key).visible(value);
  });

  services_table.responsive.recalc();

  services_table.on("mouseenter", "td", function () {
    if (services_table.cell(this).index() === undefined) return;
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

  services_table.on("select", function (e, dt, type, indexes) {
    // Enable the actions button
    $(".action-button")
      .removeClass("disabled")
      .parent()
      .attr("data-bs-toggle", null)
      .attr("data-bs-original-title", null)
      .attr("data-bs-placement", null)
      .tooltip("dispose");
  });

  services_table.on("deselect", function (e, dt, type, indexes) {
    // If no rows are selected, disable the actions button
    if (services_table.rows({ selected: true }).count() === 0) {
      $(".action-button")
        .addClass("disabled")
        .parent()
        .attr("data-bs-toggle", "tooltip")
        .attr(
          "data-bs-original-title",
          "Please select one or more rows to perform an action.",
        )
        .attr("data-bs-placement", "top")
        .tooltip();
    }
  });

  const debounce = (func, delay) => {
    let timer = null;

    return (...args) => {
      // Clear the timer if the function is called again during the delay
      if (timer) clearTimeout(timer);

      // Start a new timer to invoke the function after the delay
      timer = setTimeout(() => {
        func(...args);
      }, delay);
    };
  };

  const saveColumnsPreferences = debounce(() => {
    const rootUrl = $("#home-path")
      .val()
      .trim()
      .replace(/\/home$/, "/set_columns_preferences");
    const csrfToken = $("#csrf_token").val();

    const data = new FormData();
    data.append("csrf_token", csrfToken);
    data.append("table_name", "services");
    data.append("columns_preferences", JSON.stringify(columnVisibility));

    fetch(rootUrl, {
      method: "POST",
      body: data,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        console.log("Preferences saved successfully!");
        // Handle success, redirect, etc.
      })
      .catch((error) => {
        console.error("There was a problem with the fetch operation:", error);
      });
  }, 1000);

  services_table.on(
    "column-visibility.dt",
    function (e, settings, column, state) {
      if (column === 0 || column === 1 || column === 7) return;
      columnVisibility[column] = state;
      // Check if columVisibility is equal to defaultColsVisibility
      const isDefault =
        JSON.stringify(columnVisibility) ===
        JSON.stringify(defaultColsVisibility);
      // If it is, remove the key from localStorage
      if (isDefault) {
        localStorage.removeItem("bw-services-columns");
      } else {
        localStorage.setItem(
          "bw-services-columns",
          JSON.stringify(columnVisibility),
        );
      }

      saveColumnsPreferences();
    },
  );

  $(document).on("click", ".delete-service", function () {
    if (isReadOnly) {
      alert("This action is not allowed in read-only mode.");
      return;
    }
    const service = $(this).data("service-id");
    setupDeletionModal([service]);
  });
});
