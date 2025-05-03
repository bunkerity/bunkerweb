$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key; // Fallback

  let actionLock = false;
  const jobNumber = parseInt($("#job_number").val());
  const isReadOnly = $("#is-read-only").val().trim() === "True";

  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [3, 4, 5, 6, 7],
      },
    },
    topStart: {},
    topEnd: {
      search: true,
      buttons: [
        {
          extend: "toggle_filters",
          className: "btn btn-sm btn-outline-primary toggle-filters",
        },
      ],
    },
    bottomStart: {
      info: true,
    },
    bottomEnd: {},
  };

  if (jobNumber > 10) {
    const menu = [10];
    if (jobNumber > 25) {
      menu.push(25);
    }
    if (jobNumber > 50) {
      menu.push(50);
    }
    if (jobNumber > 100) {
      menu.push(100);
    }
    menu.push({ label: t("datatable.length_all", "All"), value: -1 });
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
      columns: "th:not(:nth-child(-n+3)):not(:last-child)",
      text: `<span class="tf-icons bx bx-columns bx-18px me-2"></span><span class="d-none d-md-inline" data-i18n="button.columns">${t(
        "button.columns",
        "Columns",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary",
      columnText: function (dt, idx, title) {
        const headerCell = dt.column(idx).header();
        const $header = $(headerCell);
        const $translatableElement = $header.find("[data-i18n]");
        let i18nKey = $translatableElement.data("i18n");
        let translatedTitle = title;
        if (i18nKey) {
          translatedTitle = t(i18nKey, title);
        } else {
          translatedTitle = $header.text().trim() || title;
        }
        return `${idx + 1}. <span data-i18n="${
          i18nKey || ""
        }">${translatedTitle}</span>`;
      },
    },
    {
      extend: "colvisRestore",
      text: `<span class="tf-icons bx bx-reset bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.reset_columns">${t(
        "button.reset_columns",
        "Reset columns",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary",
    },
    {
      extend: "collection",
      text: `<span class="tf-icons bx bx-export bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.export">${t(
        "button.export",
        "Export",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary",
      buttons: [
        {
          extend: "copy",
          text: `<span class="tf-icons bx bx-copy bx-18px me-2"></span><span data-i18n="button.copy_visible">${t(
            "button.copy_visible",
            "Copy visible",
          )}</span>`,
          exportOptions: {
            columns: ":visible:not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "csv",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV`,
          bom: true,
          filename: "bw_jobs",
          exportOptions: {
            modifier: {
              search: "none",
            },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
          filename: "bw_jobs",
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
      text: `<span class="tf-icons bx bx-play bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.actions">${t(
        "button.actions",
        "Actions",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary action-button disabled",
      buttons: [
        {
          extend: "run_jobs",
        },
      ],
    },
  ];

  const getSelectedJobs = () => {
    const jobs = [];
    $("tr.selected").each(function () {
      const $this = $(this);
      const name = $this.find("td:eq(1)").text().trim();
      const plugin = $this.find("td:eq(2)").text().trim();
      jobs.push({ name: name, plugin: plugin });
    });
    return jobs;
  };

  const executeForm = (jobs) => {
    const form = $("<form>", {
      method: "POST",
      action: `${window.location.pathname}/run`,
      class: "visually-hidden",
    });

    // Add CSRF token and jobs as hidden inputs
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
        name: "jobs",
        value: JSON.stringify(jobs),
      }),
    );

    // Append the form to the body and submit it
    form.appendTo("body").submit();
  };

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
      $(this).text(t("validation.invalid_date", "Invalid date"));
    }
  });

  $.fn.dataTable.ext.buttons.run_jobs = {
    text: `<span class="tf-icons bx bx-play bx-18px me-2"></span><span data-i18n="button.run_selected_jobs">${t(
      "button.run_selected_jobs",
      "Run selected jobs",
    )}</span>`,
    action: function (e, dt, node, config) {
      if (isReadOnly) {
        alert(
          t(
            "alert.readonly_mode",
            "This action is not allowed in read-only mode.",
          ),
        );
        return;
      }
      if (actionLock) {
        return;
      }
      actionLock = true;
      $(".dt-button-background").click();

      const jobs = getSelectedJobs();
      if (jobs.length === 0) {
        actionLock = false;
        return;
      }

      executeForm(jobs);

      actionLock = false;
    },
  };

  const jobs_config = {
    tableSelector: "#jobs",
    tableName: "jobs",
    columnVisibilityCondition: (column) => column > 2 && column < 8,
    dataTableOptions: {
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
          searchPanes: {
            show: true,
            header: t("searchpane.plugin", "Plugin"),
            combiner: "or",
          },
          targets: 3,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.interval", "Interval"),
            options: [
              {
                label: `<span data-i18n="interval.day">${t(
                  "interval.day",
                  "Every day",
                )}</span>`,
                value: (rowData) => rowData[4].includes("interval.day"),
              },
              {
                label: `<span data-i18n="interval.hour">${t(
                  "interval.hour",
                  "Every hour",
                )}</span>`,
                value: (rowData) => rowData[4].includes("interval.hour"),
              },
              {
                label: `<span data-i18n="interval.week">${t(
                  "interval.week",
                  "Every week",
                )}</span>`,
                value: (rowData) => rowData[4].includes("interval.week"),
              },
              {
                label: `<span data-i18n="interval.once">${t(
                  "interval.once",
                  "Once",
                )}</span>`,
                value: (rowData) => rowData[4].includes("interval.once"),
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 4,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.reload", "Reload"),
            options: [
              {
                label: `<i class=\"bx bx-xs bx-x text-danger\"></i>&nbsp;<span data-i18n="status.no">${t(
                  "status.no",
                  "No",
                )}</span>`,
                value: (rowData) => rowData[5].includes("bx-x"),
              },
              {
                label: `<i class=\"bx bx-xs bx-check text-success\"></i>&nbsp;<span data-i18n="status.yes">${t(
                  "status.yes",
                  "Yes",
                )}</span>`,
                value: (rowData) => rowData[5].includes("bx-check"),
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
            header: t("searchpane.async", "Async"),
            options: [
              {
                label: `<i class=\"bx bx-xs bx-x text-danger\"></i>&nbsp;<span data-i18n="status.no">${t(
                  "status.no",
                  "No",
                )}</span>`,
                value: (rowData) => rowData[6].includes("bx-x"),
              },
              {
                label: `<i class=\"bx bx-xs bx-check text-success\"></i>&nbsp;<span data-i18n="status.yes">${t(
                  "status.yes",
                  "Yes",
                )}</span>`,
                value: (rowData) => rowData[6].includes("bx-check"),
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
            header: t("searchpane.last_run", "Last run state"),
            options: [
              {
                label: `<i class=\"bx bx-xs bx-x text-danger\"></i>&nbsp;<span data-i18n="status.failed">${t(
                  "status.failed",
                  "Failed",
                )}</span>`,
                value: (rowData) => rowData[7].includes("bx-x"),
              },
              {
                label: `<i class=\"bx bx-xs bx-check text-success\"></i>&nbsp;<span data-i18n="status.success">${t(
                  "status.success",
                  "Success",
                )}</span>`,
                value: (rowData) => rowData[7].includes("bx-check"),
              },
            ],
            combiner: "or",
            orderable: false,
          },
          targets: 7,
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
      initComplete: function (settings, json) {
        $("#jobs_wrapper .btn-secondary").removeClass("btn-secondary");
      },
    },
  };

  // Wait for window.i18nextReady = true before continuing
  if (typeof window.i18nextReady === "undefined" || !window.i18nextReady) {
    const waitForI18next = (resolve) => {
      if (window.i18nextReady) {
        resolve();
      } else {
        setTimeout(() => waitForI18next(resolve), 50);
      }
    };
    new Promise((resolve) => {
      waitForI18next(resolve);
    }).then(() => initializeDataTable(jobs_config));
  }

  $(document).on("click", ".show-history", function () {
    const historyModal = $("#modal-job-history");
    const job = $(this).data("job");
    const plugin = $(this).data("plugin");

    const history = $(`#job-${job}-${plugin}-history`).clone();
    const historyCount = history.find("ul").length - 1;
    historyModal
      .find(".modal-title")
      .html(
        `${t("modal.title.job_history", "Last 10 Job's executions")}<br>` +
          `${t(
            "modal.title.job_history_count",
            "Last{{count}} execution(s) of Job",
            { count: historyCount > 1 ? " " + historyCount : "" },
          )} <span class="fw-bold fst-italic">${job}</span> ${t(
            "modal.title.from_plugin",
            "from plugin",
          )} <span class="fw-bold fst-italic">${plugin}</span>`,
      );
    history.removeClass("visually-hidden");
    historyModal.find(".modal-body").html(history);

    const modal = new bootstrap.Modal(historyModal);
    modal.show();
  });

  $(document).on("click", ".run-job", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const job = {
      name: $(this).data("job"),
      plugin: $(this).data("plugin"),
    };
    executeForm([job]);
  });
});
