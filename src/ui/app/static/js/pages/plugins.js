$(document).ready(function () {
  var actionLock = false;
  const dragArea = $("#drag-area");
  const fileInput = $("#file-input");
  const fileList = $("#file-list");
  const pluginNumber = parseInt($("#plugins_number").val());
  const isReadOnly = $("#is-read-only").val().trim() === "True";

  const setupDeletionModal = (plugins) => {
    const delete_modal = $("#modal-delete-plugins");
    const list = $(
      `<ul class="list-group list-group-horizontal w-100">
      <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
        <div class="ms-2 me-auto">
          <div class="fw-bold">Name</div>
        </div>
      </li>
      <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
        <div class="fw-bold">Version</div>
      </li>
      <li class="list-group-item bg-secondary text-white" style="flex: 1 1 0;">
        <div class="fw-bold">Type</div>
      </li>
      </ul>`,
    );
    $("#selected-plugins-delete").append(list);

    plugins.forEach((plugin) => {
      const list = $(
        `<ul class="list-group list-group-horizontal w-100"></ul>`,
      );

      // Create the list item using template literals
      const listItem = $(`<li class="list-group-item" style="flex: 1 1 0;">
  <div class="ms-2 me-auto">
    ${$(`#name-${plugin}`).html()}
  </div>
</li>`);
      list.append(listItem);

      // Clone the version element and append it to the list item
      const versionClone = $(`#version-${plugin}`).clone();
      const versionListItem = $(
        `<li class="list-group-item" style="flex: 1 1 0;"></li>`,
      );
      versionListItem.append(versionClone.removeClass("highlight"));
      list.append(versionListItem);

      // Clone the type element and append it to the list item
      const typeClone = $(`#type-${plugin}`).clone();
      const typeListItem = $(
        `<li class="list-group-item" style="flex: 1 1 0;"></li>`,
      );
      typeListItem.append(typeClone.removeClass("highlight"));
      list.append(typeListItem);
      typeClone.find('[data-bs-toggle="tooltip"]').tooltip();

      $("#selected-plugins-delete").append(list);
    });

    const modal = new bootstrap.Modal(delete_modal);
    delete_modal
      .find(".alert")
      .text(
        `Are you sure you want to delete the selected plugin${"s".repeat(
          plugins.length > 1,
        )}?`,
      );
    modal.show();

    $("#selected-plugins-input-delete").val(plugins.join(","));
  };

  // Function to validate plugin files
  const validateFile = (file) => {
    const validExtensions = [".zip", ".tar.gz", ".tar.xz"];
    const fileName = file.name.toLowerCase();
    const maxFileSize = 50 * 1024 * 1024; // 50 MB

    const isValidExtension = validExtensions.some(function (ext) {
      return fileName.endsWith(ext);
    });

    if (!isValidExtension) {
      return false;
    }

    if (file.size > maxFileSize) {
      alert("File size exceeds 50 MB limit.");
      return false;
    }

    return true;
  };

  const uploadFile = (file) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("csrf_token", $("#csrf_token").val());

    // Construct the upload URL
    const currentUrl = window.location.href.split("?")[0].split("#")[0];
    const uploadUrl = currentUrl.replace(/\/$/, "") + "/upload";

    fileSize = (file.size / 1024).toFixed(2); // Size in KB
    const fileItem = $(`
            <div class="file-item">
                <strong>${file.name}</strong> (${fileSize} KB)
            </div>
        `);
    fileList.append(fileItem);

    // Create a progress bar element
    const progressBar = $(
      '<div class="progress-bar" role="progressbar" style="width: 0%;"></div>',
    );
    const progress = $('<div class="progress mt-2"></div>').append(progressBar);
    fileList.append(progress);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", uploadUrl);

    // Update progress
    xhr.upload.addEventListener("progress", (evt) => {
      if (evt.lengthComputable) {
        const percentComplete = (evt.loaded / evt.total) * 100;
        progressBar.css("width", percentComplete + "%");
        progressBar.attr("aria-valuenow", percentComplete);
      }
    });

    xhr.onload = () => {
      if (xhr.status === 201) {
        progressBar.addClass("bg-success");
        $("#add-plugins-submit").removeClass("disabled");
        fileItem.append('<span class="text-success ms-2">Uploaded</span>');
      } else {
        progressBar.addClass("bg-danger");
        fileItem.append('<span class="text-danger ms-2">Failed</span>');
        alert("An error occurred while uploading the file. Please try again.");
      }
    };

    xhr.onerror = () => {
      console.error("Upload error:", xhr.statusText);
      progressBar.addClass("bg-danger");
      alert("An error occurred while uploading the file. Please try again.");
    };

    xhr.send(formData);
  };

  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [6, 7, 8],
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

  if (pluginNumber > 10) {
    const menu = [10];
    if (pluginNumber > 25) {
      menu.push(25);
    }
    if (pluginNumber > 50) {
      menu.push(50);
    }
    if (pluginNumber > 100) {
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
      extend: "add_plugin",
    },
    {
      extend: "colvis",
      columns: "th:not(:nth-child(-n+3))",
      text: '<span class="tf-icons bx bx-columns bx-18px me-md-2"></span><span class="d-none d-md-inline">Columns</span>',
      className: "btn btn-sm btn-outline-primary rounded-start",
      columnText: function (dt, idx, title) {
        return idx + 1 + ". " + title;
      },
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
          filename: "bw_plugins",
          exportOptions: {
            modifier: {
              search: "none",
            },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: '<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel',
          filename: "bw_plugins",
          exportOptions: {
            modifier: {
              search: "none",
            },
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
          extend: "delete_plugins",
          className: "text-danger",
        },
      ],
    },
  ];

  $("#modal-delete-plugins").on("hidden.bs.modal", function () {
    $("#selected-plugins-delete").empty();
    $("#selected-plugins-input-delete").val("");
  });

  const getSelectedPlugins = () => {
    const plugins = [];
    $("tr.selected").each(function () {
      const plugin = $(this).find("td:eq(2)").data("id");
      if (plugin) {
        plugins.push(plugin);
      }
    });
    return plugins;
  };

  $.fn.dataTable.ext.buttons.toggle_filters = {
    text: '<span class="tf-icons bx bx-filter bx-18px me-2"></span><span id="show-filters">Show</span><span id="hide-filters" class="d-none">Hide</span><span class="d-none d-md-inline"> filters</span>',
    action: function (e, dt, node, config) {
      plugins_table.searchPanes.container().slideToggle(); // Smoothly hide or show the container
      $("#show-filters").toggleClass("d-none"); // Toggle the visibility of the 'Show' span
      $("#hide-filters").toggleClass("d-none"); // Toggle the visibility of the 'Hide' span
    },
  };

  $.fn.dataTable.ext.buttons.add_plugin = {
    text: '<span class="tf-icons bx bx-plus"></span><span class="d-none d-md-inline">&nbsp;Add plugin(s)</span>',
    className: `btn btn-sm rounded me-4 btn-bw-green${
      isReadOnly ? " disabled" : ""
    }`,
    action: function (e, dt, node, config) {
      if (isReadOnly) {
        alert("This action is not allowed in read-only mode.");
        return;
      }
      const plugin_modal = $("#modal-add-plugins");
      const modal = new bootstrap.Modal(plugin_modal);
      modal.show();
    },
  };

  $.fn.dataTable.ext.buttons.delete_plugins = {
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

      const plugins = getSelectedPlugins();
      if (plugins.length === 0) {
        actionLock = false;
        return;
      }

      setupDeletionModal(plugins);

      actionLock = false;
    },
  };

  const plugins_table = new DataTable("#plugins", {
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
      {
        orderable: false,
        targets: -1,
      },
      {
        visible: false,
        targets: [2, 4],
      },
      {
        searchPanes: {
          show: true,
          header: "Stream Support",
          options: [
            {
              label: '<i class="bx bx-xs bx-x text-danger"></i>&nbsp;No',
              value: function (rowData, rowIdx) {
                return rowData[6].includes("bx-x");
              },
            },
            {
              label: '<i class="bx bx-xs bx-check text-success"></i>&nbsp;Yes',
              value: function (rowData, rowIdx) {
                return rowData[6].includes("bx-check");
              },
            },
            {
              label:
                '<i class="bx bx-xs bx-minus text-warning"></i>&nbsp;Partial',
              value: function (rowData, rowIdx) {
                return rowData[6].includes("bx-minus");
              },
            },
          ],
          combiner: "or",
          orderable: false,
        },
        targets: 6,
      },
      {
        searchPanes: {
          show: true,
          options: [
            {
              label: `<img src="${$("#pro_diamond_url")
                .val()
                .trim()}" alt="Pro plugin" width="16px" height="12.9125px" class="mb-1">&nbsp;PRO`,
              value: function (rowData, rowIdx) {
                return rowData[7].includes("PRO");
              },
            },
            {
              label: '<i class="bx bx-plug bx-xs"></i>&nbsp;External',
              value: function (rowData, rowIdx) {
                return rowData[7].includes("EXTERNAL");
              },
            },
            {
              label: '<i class="bx bx-cloud-upload bx-xs"></i>&nbsp;UI',
              value: function (rowData, rowIdx) {
                return rowData[7].includes("UI");
              },
            },
            {
              label: '<i class="bx bx-shield bx-xs"></i>&nbsp;Core',
              value: function (rowData, rowIdx) {
                return rowData[7].includes("CORE");
              },
            },
          ],
          combiner: "or",
          orderable: false,
        },
        targets: 7,
      },
      {
        searchPanes: {
          show: true,
          combiner: "or",
          orderable: false,
        },
        targets: 8,
      },
    ],
    order: [[3, "asc"]],
    autoFill: false,
    responsive: true,
    select: {
      style: "multi+shift",
      selector: "td:nth-child(2)",
      headerCheckbox: true,
    },
    layout: layout,
    language: {
      info: "Showing _START_ to _END_ of _TOTAL_ plugins",
      infoEmpty: "No plugins available",
      infoFiltered: "(filtered from _MAX_ total plugins)",
      lengthMenu: "Display _MENU_ plugins",
      zeroRecords: "No matching plugins found",
      select: {
        rows: {
          _: "Selected %d plugins",
          0: "No plugins selected",
          1: "Selected 1 plugin",
        },
      },
    },
    initComplete: function (settings, json) {
      $("#plugins_wrapper .btn-secondary").removeClass("btn-secondary");
      if (isReadOnly)
        $("#plugins_wrapper .dt-buttons")
          .attr(
            "data-bs-original-title",
            "The database is in readonly, therefore you cannot create add plugins.",
          )
          .attr("data-bs-placement", "right")
          .tooltip();
    },
  });

  plugins_table.searchPanes.container().hide();

  $(".action-button")
    .parent()
    .attr(
      "data-bs-original-title",
      "Please select one or more rows to perform an action.",
    )
    .attr("data-bs-placement", "top")
    .tooltip();

  $("#plugins").removeClass("d-none");
  $("#plugins-waiting").addClass("visually-hidden");

  plugins_table.responsive.recalc();

  plugins_table.on("mouseenter", "td", function () {
    if (plugins_table.cell(this).index() === undefined) return;
    const rowIdx = plugins_table.cell(this).index().row;

    plugins_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));

    plugins_table
      .cells()
      .nodes()
      .each(function (el) {
        if (plugins_table.cell(el).index().row === rowIdx)
          el.classList.add("highlight");
      });
  });

  plugins_table.on("mouseleave", "td", function () {
    plugins_table
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));
  });

  plugins_table.on("select", function (e, dt, type, indexes) {
    // Enable the actions button
    $(".action-button")
      .removeClass("disabled")
      .parent()
      .attr("data-bs-toggle", null)
      .attr("data-bs-original-title", null)
      .attr("data-bs-placement", null)
      .tooltip("dispose");
  });

  plugins_table.on("deselect", function (e, dt, type, indexes) {
    // If no rows are selected, disable the actions button
    if (plugins_table.rows({ selected: true }).count() === 0) {
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

  $(document).on("click", ".delete-plugin", function () {
    if (isReadOnly) {
      alert("This action is not allowed in read-only mode.");
      return;
    }
    $this = $(this);
    setupDeletionModal([$this.data("plugin-id")]);
  });

  // Open file dialog on click
  dragArea.on("click", function () {
    fileInput.click();
  });

  // Handle drag over
  dragArea.on("dragover", function (e) {
    e.preventDefault();
    dragArea.removeClass("border-dashed");
    dragArea.addClass("bg-primary text-white");
    dragArea.find("i").removeClass("text-primary");
  });

  // Handle drag leave
  dragArea.on("dragleave", function (e) {
    e.preventDefault();
    dragArea.addClass("border-dashed");
    dragArea.removeClass("bg-primary text-white");
    dragArea.find("i").addClass("text-primary");
  });

  // File input change event
  fileInput.on("change", function () {
    for (let i = 0; i < fileInput.get(0).files.length; i++) {
      setTimeout(() => {
        const file = fileInput.get(0).files[i];
        if (validateFile(file)) {
          uploadFile(file);
        } else {
          alert("Please upload a valid plugin file (.zip, .tar.gz, .tar.xz).");
        }
      }, 500 * i);
    }
  });

  // Handle drop
  dragArea.on("drop", function (e) {
    e.preventDefault();
    dragArea.addClass("border-dashed");
    dragArea.removeClass("bg-primary text-white");
    dragArea.find("i").addClass("text-primary");
    fileInput.prop("files", e.originalEvent.dataTransfer.files);
    fileInput.trigger("change");
  });
});
