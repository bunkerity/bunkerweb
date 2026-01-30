$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key; // Fallback

  var actionLock = false;
  let addBanNumber = 1;
  const baseFlagsUrl = $("#base_flags_url").val().trim();
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const userReadOnly = $("#user-read-only").val().trim() === "True";

  const headers = [
    {
      title: "Date",
      tooltip: "The date and time when the Ban was created",
      i18n: "tooltip.table.bans.date",
    },
    {
      title: "IP Address",
      tooltip: "The banned IP address",
      i18n: "tooltip.table.bans.ip_address",
    },
    {
      title: "Country",
      tooltip: "The banned IP country",
      i18n: "tooltip.table.bans.country",
    },
    {
      title: "Reason",
      tooltip: "The reason why the Report was created",
      i18n: "tooltip.table.bans.reason",
    },
    {
      title: "Scope",
      tooltip: "The scope of the ban (global or service-specific)",
      i18n: "tooltip.table.bans.scope",
    },
    {
      title: "Service",
      tooltip: "The service that created the ban",
      i18n: "tooltip.table.bans.service",
    },
    {
      title: "End date",
      tooltip: "The end date of the Ban",
      i18n: "tooltip.table.bans.end_date",
    },
    {
      title: "Time left",
      tooltip: "The time left until the Ban expires",
      i18n: "tooltip.table.bans.time_left",
    },
    {
      title: "Actions",
      tooltip: "Actions that can be performed on the ban",
      i18n: "tooltip.table.bans.actions",
    },
  ];

  // Batch update tooltips
  const updateCountryTooltips = () => {
    $("[data-country]").each(function () {
      const $elem = $(this);
      const countryCode = $elem.data("country");

      const countryName = t(
        countryCode === "unknown" || countryCode === "local"
          ? "country.not_applicable"
          : `country.${countryCode}`,
        "Unknown",
      );
      if (countryName && countryName !== "country.not_applicable") {
        $elem.attr("data-bs-original-title", countryName);
      }
    });
    $('[data-bs-toggle="tooltip"]').tooltip("dispose").tooltip();
  };

  // Utility functions
  function addDays(date, days) {
    const result = new Date(date);
    result.setDate(result.getDate() + days);
    return result;
  }

  function addHours(date, hours) {
    const result = new Date(date);
    result.setHours(result.getHours() + hours);
    return result;
  }

  function formatDate(date) {
    const year = date.getFullYear();
    let month = date.getMonth() + 1; // Months are zero-based in JavaScript
    let day = date.getDate();

    // Pad month and day with leading zeros if needed
    month = month < 10 ? "0" + month : month;
    day = day < 10 ? "0" + day : day;

    return `${year}-${month}-${day}`;
  }

  function formatTime(date) {
    let hours = date.getHours();
    let minutes = date.getMinutes();

    // Pad hours and minutes with leading zeros if needed
    hours = hours < 10 ? "0" + hours : hours;
    minutes = minutes < 10 ? "0" + minutes : minutes;

    return `${hours}:${minutes}`;
  }

  // Select the Flatpickr input elements
  const flatpickrDatetime = $("[type='flatpickr-datetime']");

  // Get the current date and times
  const currentDatetime = new Date();
  const minDatetime = addHours(currentDatetime, 1);
  const defaultDatetime = addDays(currentDatetime, 1);

  // Format dates and times
  const minDateStr = formatDate(minDatetime);
  const minTimeStr = formatTime(minDatetime);

  // Create the minMaxTime table
  const minMaxTable = {
    [minDateStr]: {
      minTime: minTimeStr,
    },
  };

  const getTimeZoneOffset = () => {
    const offset = -currentDatetime.getTimezoneOffset(); // getTimezoneOffset returns minutes behind UTC
    const sign = offset >= 0 ? "+" : "-";
    const absOffset = Math.abs(offset);
    const hours = String(Math.floor(absOffset / 60)).padStart(2, "0");
    const minutes = String(absOffset % 60).padStart(2, "0");
    return `${sign}${hours}:${minutes}`;
  };

  // Initialize Flatpickr with altInput and altFormat
  const originalFlatpickr = flatpickrDatetime.flatpickr({
    enableTime: true,
    dateFormat: "Y-m-d\\TH:i:S", // ISO format
    altInput: true,
    altFormat: "F j, Y h:i K", // User-friendly display format
    time_24hr: true,
    defaultDate: defaultDatetime,
    minDate: minDatetime,
    plugins: [
      new minMaxTimePlugin({
        table: minMaxTable,
      }),
    ],
  });

  // Function to set up the unban modal
  const setupUnbanModal = (bans) => {
    const $modalBody = $("#selected-ips-unban");
    $modalBody.empty(); // Clear previous content

    // Create and append the header row
    const $header = $(`
      <ul class="list-group list-group-horizontal w-100">
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold" data-i18n="table.header.ip_address">${t(
              "table.header.ip_address",
            )}</div>
          </div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="fw-bold" data-i18n="table.header.scope">${t(
            "table.header.scope",
          )}</div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="fw-bold" data-i18n="table.header.time_left">${t(
            "table.header.time_left",
          )}</div>
        </li>
      </ul>
    `);
    $modalBody.append($header);

    // Iterate over bans and append list items
    bans.forEach((ban) => {
      const scopeText =
        ban.ban_scope === "global"
          ? t("scope.global", "Global")
          : t("scope.service_specific", "Service-specific");
      const serviceText =
        ban.service && ban.ban_scope === "service" ? ` (${ban.service})` : "";

      const $row = $(`
        <ul class="list-group list-group-horizontal w-100">
          <li class="list-group-item" style="flex: 1 0;">
            <div class="ms-2 me-auto">
              <div class="fw-bold">${ban.ip}</div>
            </div>
          </li>
          <li class="list-group-item" style="flex: 1 0;">
            <div class="ms-2 me-auto">
              ${scopeText}${serviceText}
            </div>
          </li>
          <li class="list-group-item" style="flex: 1 0;">
            <div class="ms-2 me-auto">
              ${ban.time_remaining}
            </div>
          </li>
        </ul>
      `);
      $modalBody.append($row);
    });

    // Show the modal
    const $unbanModal = $("#modal-unban-ips");
    const modalInstance = new bootstrap.Modal($unbanModal[0]);

    // Update the alert text using i18next (assuming keys exist)
    const alertTextKey =
      bans.length > 1
        ? "modal.body.unban_confirmation_alert_plural"
        : "modal.body.unban_confirmation_alert";
    $unbanModal
      .find(".alert")
      .attr("data-i18n", alertTextKey)
      .text(
        t(
          alertTextKey,
          "Are you sure you want to unban the selected IP address(es)?",
        ),
      );

    modalInstance.show();

    // Set the hidden input value
    $("#selected-ips-input-unban").val(JSON.stringify(bans));
  };

  // Function to set up the update duration modal
  const setupUpdateDurationModal = (bans) => {
    const $modalBody = $("#selected-ips-update-duration");
    $modalBody.empty(); // Clear previous content

    // Create and append the header row
    const $header = $(`
      <ul class="list-group list-group-horizontal w-100">
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="ms-2 me-auto">
            <div class="fw-bold" data-i18n="table.header.ip_address">${t(
              "table.header.ip_address",
            )}</div>
          </div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="fw-bold" data-i18n="table.header.scope">${t(
            "table.header.scope",
          )}</div>
        </li>
        <li class="list-group-item bg-secondary text-white" style="flex: 1 0;">
          <div class="fw-bold" data-i18n="table.header.current_time_left">${t(
            "table.header.current_time_left",
          )}</div>
        </li>
      </ul>
    `);
    $modalBody.append($header);

    // Iterate over bans and append list items
    bans.forEach((ban) => {
      const scopeText =
        ban.ban_scope === "global"
          ? t("scope.global", "Global")
          : t("scope.service_specific", "Service-specific");
      const serviceText =
        ban.service && ban.ban_scope === "service" ? ` (${ban.service})` : "";

      const $row = $(`
        <ul class="list-group list-group-horizontal w-100">
          <li class="list-group-item" style="flex: 1 0;">
            <div class="ms-2 me-auto">
              <div class="fw-bold">${ban.ip}</div>
            </div>
          </li>
          <li class="list-group-item" style="flex: 1 0;">
            <div class="ms-2 me-auto">
              ${scopeText}${serviceText}
            </div>
          </li>
          <li class="list-group-item" style="flex: 1 0;">
            <div class="ms-2 me-auto">
              ${ban.time_remaining}
            </div>
          </li>
        </ul>
      `);
      $modalBody.append($row);
    });

    // Show the modal
    const $updateDurationModal = $("#modal-update-duration");
    const modalInstance = new bootstrap.Modal($updateDurationModal[0]);
    modalInstance.show();

    // Set the hidden input value
    $("#selected-ips-input-update-duration").val(JSON.stringify(bans));

    // Initialize flatpickr for custom duration after modal is shown
    const customEndDateInput = $("#custom-end-date");
    if (!customEndDateInput[0]._flatpickr) {
      customEndDateInput.flatpickr({
        enableTime: true,
        dateFormat: "Y-m-d\\TH:i:S",
        altInput: true,
        altFormat: "F j, Y h:i K",
        time_24hr: true,
        defaultDate: defaultDatetime,
        minDate: minDatetime,
        plugins: [new minMaxTimePlugin({ table: minMaxTable })],
      });
    }
  };

  // Handle duration select change to show/hide custom fields
  $(document).on("change", "#duration-select", function () {
    const $customFields = $("#custom-duration-fields");
    const $customEndDate = $("#custom-end-date");

    if ($(this).val() === "custom") {
      $customFields.show();
      $customEndDate.prop("required", true);
    } else {
      $customFields.hide();
      $customEndDate.prop("required", false);
    }
  });

  // Handle update duration form submission
  $(document).on("submit", "#modal-update-duration form", function (e) {
    e.preventDefault();

    const duration = $("#duration-select").val();
    const bansData = JSON.parse($("#selected-ips-input-update-duration").val());

    // Prepare updates array
    const updates = bansData
      .map((ban) => {
        const update = {
          ip: ban.ip,
          duration: duration,
          ban_scope: ban.ban_scope,
          service: ban.service,
        };

        // Add custom duration data if applicable
        if (duration === "custom") {
          const customEndDate = $("#custom-end-date").val();
          if (!customEndDate) {
            alert(
              t(
                "alert.custom_end_date_required",
                "Please select a custom end date.",
              ),
            );
            return null;
          }
          const customEndDateWithOffset = `${customEndDate}${getTimeZoneOffset()}`;
          update.end_date = customEndDateWithOffset;
          update.custom_exp = Math.max(
            0,
            Math.floor(
              new Date(customEndDateWithOffset).getTime() / 1000 -
                Date.now() / 1000,
            ),
          );
        }

        return update;
      })
      .filter((update) => update !== null);

    if (updates.length === 0) {
      return;
    }

    // Create and submit the form
    const form = $("<form>", {
      method: "POST",
      action: `${window.location.pathname}/update_duration`,
      class: "visually-hidden",
    });
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
        name: "updates",
        value: JSON.stringify(updates),
      }),
    );
    form.appendTo("body").submit();
  });

  // DataTable Layout and Buttons
  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [2, 4, 6, 7, 8],
      },
    },
    topStart: {},
    topEnd: {
      search: true,
      buttons: [
        {
          extend: "auto_refresh",
          className: "btn btn-sm btn-outline-primary d-flex align-items-center",
        },
        {
          extend: "toggle_filters",
          className: "btn btn-sm btn-outline-primary toggle-filters",
        },
      ],
    },
    bottomStart: {
      pageLength: {
        menu: [10, 25, 50, 100, { label: "All", value: -1 }],
      },
      info: true,
    },
  };

  layout.topStart.buttons = [
    { extend: "add_ban" },
    {
      extend: "colvis",
      columns: "th:not(:nth-child(-n+3))",
      text: `<span class="tf-icons bx bx-columns bx-18px me-md-2"></span><span class="d-none d-md-inline" data-i18n="button.columns">${t(
        "button.columns",
        "Columns",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary rounded-start",
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
      text: `<span class="tf-icons bx bx-reset bx-18px me-2"></span><span class="d-none d-md-inline" data-i18n="button.reset_columns">${t(
        "button.reset_columns",
        "Reset columns",
      )}</span>`,
      className: "btn btn-sm btn-outline-primary d-none d-md-inline",
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
          filename: "bw_bans",
          exportOptions: {
            modifier: { search: "none" },
            columns: ":not(:nth-child(-n+2)):not(:last-child)",
          },
        },
        {
          extend: "excel",
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
          filename: "bw_bans",
          exportOptions: {
            modifier: { search: "none" },
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
        { extend: "unban_ips", className: "text-danger" },
        {
          text: `<span class="tf-icons bx bx-timer bx-18px me-2"></span><span data-i18n="button.update_duration">${t(
            "button.update_duration",
            "Update Duration",
          )}</span>`,
          className: "text-warning",
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
            if (actionLock) return;
            actionLock = true;
            $(".dt-button-background").click();

            const bans = getSelectedBans();
            if (bans.length === 0) {
              actionLock = false;
              return;
            }
            setupUpdateDurationModal(bans);
            actionLock = false;
          },
        },
        "separator",
        {
          text: `<span class="tf-icons bx bx-time-five bx-18px me-2"></span><span data-i18n="button.set_1h">${t(
            "button.set_1h",
            "Set 1 Hour",
          )}</span>`,
          action: (e, dt, node, config) => {
            updateSelectedBansDuration("1h");
          },
        },
        {
          text: `<span class="tf-icons bx bx-time bx-18px me-2"></span><span data-i18n="button.set_24h">${t(
            "button.set_24h",
            "Set 24 Hours",
          )}</span>`,
          action: (e, dt, node, config) => {
            updateSelectedBansDuration("24h");
          },
        },
        {
          text: `<span class="tf-icons bx bx-calendar-week bx-18px me-2"></span><span data-i18n="button.set_1w">${t(
            "button.set_1w",
            "Set 1 Week",
          )}</span>`,
          action: (e, dt, node, config) => {
            updateSelectedBansDuration("1w");
          },
        },
        {
          text: `<span class="tf-icons bx bx-infinite bx-18px me-2"></span><span data-i18n="button.set_permanent">${t(
            "button.set_permanent",
            "Set Permanent",
          )}</span>`,
          className: "text-danger",
          action: (e, dt, node, config) => {
            updateSelectedBansDuration("permanent");
          },
        },
      ],
    },
  ];

  let autoRefresh = false;
  let autoRefreshInterval = null;
  const sessionAutoRefresh = sessionStorage.getItem("bansAutoRefresh");

  function toggleAutoRefresh() {
    autoRefresh = !autoRefresh;
    sessionStorage.setItem("bansAutoRefresh", autoRefresh);
    if (autoRefresh) {
      $(".bx-loader")
        .addClass("bx-spin")
        .closest(".btn")
        .removeClass("btn-outline-primary")
        .addClass("btn-primary");
      if (autoRefreshInterval) clearInterval(autoRefreshInterval);
      autoRefreshInterval = setInterval(() => {
        if (!autoRefresh) {
          clearInterval(autoRefreshInterval);
          autoRefreshInterval = null;
        } else {
          $("#bans").DataTable().ajax.reload(null, false);
        }
      }, 10000); // 10 seconds
    } else {
      $(".bx-loader")
        .removeClass("bx-spin")
        .closest(".btn")
        .removeClass("btn-primary")
        .addClass("btn-outline-primary");
      if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
      }
    }
  }

  if (sessionAutoRefresh === "true") {
    toggleAutoRefresh();
  }

  $("#modal-unban-ips").on("hidden.bs.modal", function () {
    $("#selected-ips-unban").empty();
    $("#selected-ips-input-unban").val("");
  });

  $("#modal-update-duration").on("hidden.bs.modal", function () {
    $("#selected-ips-update-duration").empty();
    $("#selected-ips-input-update-duration").val("");
    // Reset form
    $("#duration-select").val("1h");
    $("#custom-duration-fields").hide();
    $("#custom-end-date").val("");
  });

  // Function to update selected bans duration
  const updateSelectedBansDuration = (duration) => {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    if (actionLock) return;
    actionLock = true;
    $(".dt-button-background").click();

    const bans = getSelectedBans();
    if (bans.length === 0) {
      actionLock = false;
      return;
    }

    // Map ban data to update format
    const updates = bans.map((ban) => ({
      ip: ban.ip,
      duration: duration,
      ban_scope: ban.ban_scope,
      service: ban.service,
    }));

    // Create and submit the form
    const form = $("<form>", {
      method: "POST",
      action: `${window.location.pathname}/update_duration`,
      class: "visually-hidden",
    });
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
        name: "updates",
        value: JSON.stringify(updates),
      }),
    );
    form.appendTo("body").submit();
    actionLock = false;
  };

  const getSelectedBans = () => {
    const bans = [];
    $("tr.selected").each(function () {
      const $row = $(this);
      const ip = $row.find("td:eq(3)").text().trim();
      const time_remaining = $row.find("td:eq(9)").text().trim();
      const scopeHtml = $row.find("td:eq(6)").html();
      const serviceHtml = $row.find("td:eq(7)").html();

      // Extract scope text, handling potential badge structure
      const scopeText = $(scopeHtml).find("span[data-i18n]").length
        ? $(scopeHtml).find("span[data-i18n]").text().trim()
        : $(scopeHtml).text().trim();

      // Extract service text, handling potential links or static text
      const serviceText = $(serviceHtml).find("strong").length
        ? $(serviceHtml).find("strong").text().trim()
        : $(serviceHtml).find("span[data-i18n]").length
          ? $(serviceHtml).find("span[data-i18n]").text().trim()
          : $(serviceHtml).text().trim();

      const ban_scope =
        scopeText === t("scope.global", "Global") ? "global" : "service";
      const service =
        serviceText === t("scope.all_services", "All services")
          ? null
          : serviceText;

      bans.push({
        ip: ip,
        time_remaining: time_remaining,
        ban_scope: ban_scope,
        service: service,
      });
    });
    return bans;
  };

  $.fn.dataTable.ext.buttons.auto_refresh = {
    text: '<span class="bx bx-loader bx-18px lh-1"></span>&nbsp;&nbsp;<span data-i18n="button.auto_refresh">Auto refresh</span>',
    action: (e, dt, node, config) => {
      toggleAutoRefresh();
    },
  };

  // Custom Button Definitions
  $.fn.dataTable.ext.buttons.add_ban = {
    text: `<span class="tf-icons bx bx-plus"></span><span class="d-none d-md-inline" data-i18n="button.add_ban_plural"> ${t(
      "button.add_ban_plural",
      "Add ban(s)",
    )}</span>`,
    className: `btn btn-sm rounded me-4 btn-bw-green${
      isReadOnly ? " disabled" : ""
    }`,
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
      const ban_modal = $("#modal-ban-ips");
      const modal = new bootstrap.Modal(ban_modal);
      modal.show();
    },
  };

  $.fn.dataTable.ext.buttons.unban_ips = {
    text: `<span class="tf-icons bx bxs-buoy bx-18px me-2"></span><span data-i18n="button.unban">${t(
      "button.unban",
      "Unban",
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
      if (actionLock) return;
      actionLock = true;
      $(".dt-button-background").click();

      const bans = getSelectedBans();
      if (bans.length === 0) {
        actionLock = false;
        return;
      }
      setupUnbanModal(bans);
      actionLock = false;
    },
  };

  const bans_config = {
    tableSelector: "#bans",
    tableName: "bans",
    columnVisibilityCondition: (column) => column > 2 && column < 11,
    dataTableOptions: {
      columnDefs: [
        { orderable: false, className: "dtr-control", targets: 0 },
        { orderable: false, render: DataTable.render.select(), targets: 1 },
        { orderable: false, targets: -1 },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.date", "Date"),
            combiner: "or",
            orderable: false,
          },
          targets: 2,
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
          type: "ip-address",
          targets: 3,
        },
        {
          searchPanes: {
            show: true,
            combiner: "or",
            header: t("searchpane.country", "Country"),
          },
          targets: 4,
          render: function (data) {
            const countryCode = data.toLowerCase();
            const isNotApplicable =
              countryCode === "unknown" ||
              countryCode === "local" ||
              countryCode === "n/a";
            const tooltipContent = "N/A";
            return `
              <span data-bs-toggle="tooltip" data-bs-original-title="${tooltipContent}" data-i18n="country.${
                isNotApplicable ? "not_applicable" : countryCode.toUpperCase()
              }" data-country="${
                isNotApplicable ? "unknown" : countryCode.toUpperCase()
              }">
              <img src="${baseFlagsUrl}/${
                isNotApplicable ? "zz" : countryCode
              }.svg"
                 class="border border-1 p-0 me-1"
                 height="17"
                 loading="lazy" />
              &nbsp;－&nbsp;${isNotApplicable ? "N/A" : data}
              </span>`;
          },
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.scope", "Scope"),
            combiner: "or",
            orderable: false,
          },
          targets: 6,
          render: function (data, type, row) {
            if (data === "service") {
              return `<span class="badge bg-info">
                <i class="bx bx-server me-1"></i>
                <span data-i18n="scope.service_specific">${t(
                  "scope.service_specific",
                  "Service",
                )}</span>
              </span>`;
            } else {
              return `<span class="badge bg-primary">
                <i class="bx bx-globe me-1"></i>
                <span data-i18n="scope.global">${t(
                  "scope.global",
                  "Global",
                )}</span>
              </span>`;
            }
          },
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.service", "Service"),
          },
          targets: 7,
          render: function (data, type, row) {
            const scope = row["scope"];
            const service = data;
            if (scope === "service") {
              const serviceLabel =
                service === "_" || !service
                  ? t("status.default_server", "default server")
                  : service;
              return `<strong>${serviceLabel}</strong>`;
            } else {
              return `<span class="text-muted fst-italic" data-i18n="scope.all_services">${t(
                "scope.all_services",
                "All services",
              )}</span>`;
            }
          },
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.end_date", "End Date"),
            combiner: "or",
            orderable: false,
          },
          targets: 8,
          render: function (data, type, row) {
            if (data === "permanent" || row["permanent"] === true) {
              return `<span class="badge bg-danger">
                <i class="bx bx-time-five me-1"></i>
                <span data-i18n="scope.permanent">${t(
                  "scope.permanent",
                  "Permanent",
                )}</span>
              </span>`;
            }
            const date = new Date(data);
            if (!isNaN(date.getTime())) {
              return date.toLocaleString();
            }
            return data;
          },
        },
        {
          targets: 9,
          render: function (data, type, row) {
            if (data === "permanent" || row["permanent"] === true) {
              return `<span class="badge bg-danger">
              <i class="bx bx-infinite me-1"></i>
              <span data-i18n="scope.permanent">${t(
                "scope.permanent",
                "Permanent",
              )}</span>
              </span>`;
            }
            const date = new Date(data);
            if (!isNaN(date.getTime())) {
              return date.toLocaleString();
            }
            return data;
          },
        },
        {
          targets: 10, // Actions column
          render: function (data, type, row) {
            if (type === "display") {
              const readOnlyClass = isReadOnly ? " disabled" : "";
              const unbanTooltip = isReadOnly
                ? t(
                    "tooltip.readonly_mode",
                    "This action is not allowed in read-only mode.",
                  )
                : t("tooltip.button.unban_ip", "Unban this IP address");
              const updateTooltip = isReadOnly
                ? t(
                    "tooltip.readonly_mode",
                    "This action is not allowed in read-only mode.",
                  )
                : t(
                    "tooltip.button.update_ban_duration",
                    "Update ban duration",
                  );

              return `
                <div class="d-flex justify-content-evenly">
                  <button type="button"
                          class="btn btn-outline-danger btn-sm me-1 unban-single${readOnlyClass}"
                          data-ip="${row.ip}"
                          data-scope="${row.scope}"
                          data-service="${row.service}"
                          data-bs-toggle="tooltip"
                          data-bs-placement="bottom"
                          data-bs-original-title="${unbanTooltip}">
                    <i class="bx bxs-buoy bx-xs"></i>
                  </button>
                  <button type="button"
                          class="btn btn-outline-warning btn-sm me-1 update-duration-single${readOnlyClass}"
                          data-ip="${row.ip}"
                          data-scope="${row.scope}"
                          data-service="${row.service}"
                          data-permanent="${row.permanent}"
                          data-bs-toggle="tooltip"
                          data-bs-placement="bottom"
                          data-bs-original-title="${updateTooltip}">
                    <i class="bx bx-timer bx-xs"></i>
                  </button>
                </div>
              `;
            }
            return "";
          },
        },
      ],
      order: [[2, "desc"]],
      autoFill: false,
      responsive: true,
      select: {
        style: "multi+shift",
        selector: "td:nth-child(2)",
        headerCheckbox: true,
      },
      layout: layout,
      processing: true,
      serverSide: true,
      ajax: {
        url: `${window.location.pathname}/fetch`,
        type: "POST",
        data: function (d) {
          d.csrf_token = $("#csrf_token").val(); // Add CSRF token if needed
          return d;
        },
        // Add error handling for ajax requests
        error: function (jqXHR, textStatus, errorThrown) {
          console.error("DataTables AJAX error:", textStatus, errorThrown);
          $("#bans").addClass("d-none");
          $("#bans-waiting")
            .removeClass("visually-hidden")
            .addClass("text-danger")
            .text(
              t(
                "status.error_loading_bans",
                "Error loading bans. Please try refreshing the page.",
              ),
            );
          // Remove any loading indicators
          $(".dataTables_processing").hide();
        },
      },
      columns: [
        {
          data: null,
          defaultContent: "",
          orderable: false,
          className: "dtr-control",
        },
        { data: null, defaultContent: "", orderable: false },
        {
          data: "date",
          title: "<span data-i18n='table.header.date'>Date</span>",
        },
        {
          data: "ip",
          title: "<span data-i18n='table.header.ip_address'>IP Address</span>",
        },
        {
          data: "country",
          title: "<span data-i18n='table.header.country'>Country</span>",
        },
        {
          data: "reason",
          title: "<span data-i18n='table.header.reason'>Reason</span>",
        },
        {
          data: "scope",
          title: "<span data-i18n='table.header.scope'>Scope</span>",
        },
        {
          data: "service",
          title: "<span data-i18n='table.header.service'>Service</span>",
        },
        {
          data: "end_date",
          title: "<span data-i18n='table.header.end_date'>End Date</span>",
        },
        {
          data: "time_left",
          title: "<span data-i18n='table.header.time_left'>Time Left</span>",
        },
        {
          data: "actions",
          title: "<span data-i18n='table.header.actions'>Actions</span>",
          orderable: false,
        },
      ],
      initComplete: function (settings, json) {
        $("#bans_wrapper .btn-secondary").removeClass("btn-secondary");
        if (isReadOnly) {
          const titleKey = userReadOnly
            ? "tooltip.readonly_user_action_disabled"
            : "tooltip.readonly_db_action_disabled";
          const defaultTitle = userReadOnly
            ? "Your account is readonly, action disabled."
            : "The database is in readonly, action disabled.";
          $("#bans_wrapper .dt-buttons")
            .attr(
              "data-bs-original-title",
              t(titleKey, defaultTitle, {
                action: t("button.add_ban_plural"),
              }),
            )
            .attr("data-bs-placement", "right")
            .tooltip();
        }
        throttle(updateCountryTooltips, 200);
      },
      headerCallback: function (thead) {
        throttle(updateHeaderTooltips, 200, thead, headers);
      },
    },
  };

  // Add a fallback timeout to prevent infinite loading
  setTimeout(function () {
    if ($("#bans").hasClass("d-none")) {
      $("#bans-waiting")
        .removeClass("visually-hidden")
        .addClass("text-danger")
        .text(
          t(
            "status.error_loading_bans",
            "Error loading bans. Please try refreshing the page.",
          ),
        );
      $("#bans").addClass("d-none");
    }
  }, 5000); // 5 seconds fallback

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
    }).then(() => {
      const dt = initializeDataTable(bans_config);
      dt.on("draw.dt", function () {
        throttle(updateCountryTooltips, 200);
        throttle(updateHeaderTooltips, 200, dt.table().header(), headers);
        $(".tooltip").remove();
        // Hide waiting message and show table
        $("#bans-waiting").addClass("visually-hidden");
        $("#bans").removeClass("d-none");
      });
      dt.on("column-visibility.dt", function (e, settings, column, state) {
        throttle(updateHeaderTooltips, 200, dt.table().header(), headers);
        $(".tooltip").remove();
      });
      // Ensure tooltips are set after initialization
      throttle(updateHeaderTooltips, 200, dt.table().header(), headers);
      // Hide waiting message and show table
      $("#bans-waiting").addClass("visually-hidden");
      $("#bans").removeClass("d-none");
      return dt;
    });
  }

  // Utility function to manage header tooltips
  function updateHeaderTooltips(selector, headers) {
    $(selector)
      .find("th")
      .each((index, element) => {
        const $th = $(element);
        // Try to get the data-i18n attribute from the header's span
        const i18nKey =
          $th.find("[data-i18n]").data("i18n") || $th.data("i18n");
        if (i18nKey) {
          const header = headers.find(
            (h) =>
              h.i18n ===
              i18nKey.replace("table.header.", "tooltip.table.bans."),
          );
          if (header) {
            $th.attr({
              "data-bs-toggle": "tooltip",
              "data-bs-placement": "bottom",
              "data-i18n": header.i18n,
              title: header.tooltip,
            });
          }
        }
      });
    applyTranslations();
    $('[data-bs-toggle="tooltip"]').tooltip("dispose").tooltip();
  }

  $("#add-ban").on("click", function () {
    const originalBan = $("#ban-1");
    const lastBan = $("#bans-container").find("li.ban-item:last");
    const banClone = originalBan.clone();
    banClone.attr("id", `ban-${++addBanNumber}`);

    banClone
      .find("input[name='ip']")
      .removeClass("is-valid is-invalid")
      .val("");

    banClone.find("[readonly='readonly']").remove();

    const lastReason = lastBan.find("input[name='reason']").val();
    banClone.find("input[name='reason']").val(lastReason || "ui");

    const lastScope = lastBan.find("select[name='ban_scope']").val();
    banClone.find("select[name='ban_scope']").val(lastScope || "global");

    if (lastScope === "service") {
      const lastService = lastBan.find("select[name='service']").val();
      banClone.find("select[name='service']").val(lastService || "");
      banClone.find(".service-field").addClass("show");
    } else {
      banClone.find(".service-field").removeClass("show");
    }

    const isPermanent = lastBan.find(".permanent-ban-checkbox").is(":checked");
    banClone.find(".permanent-ban-checkbox").prop("checked", isPermanent);

    let defaultDate;
    if (!isPermanent) {
      const lastBanFlatpickr = lastBan.find(".flatpickr-input")[0]._flatpickr;
      defaultDate = lastBanFlatpickr
        ? lastBanFlatpickr.selectedDates[0]
        : defaultDatetime;
    } else {
      defaultDate = defaultDatetime;
    }

    banClone.find(".flatpickr-input").flatpickr({
      enableTime: true,
      dateFormat: "Y-m-d\\TH:i:S", // ISO format
      altInput: true,
      altFormat: "F j, Y h:i K",
      time_24hr: true,
      defaultDate: defaultDate,
      minDate: minDatetime,
      plugins: [new minMaxTimePlugin({ table: minMaxTable })],
    });

    banClone.find("[type='flatpickr-datetime']").prop("disabled", isPermanent);
    if (isPermanent) {
      banClone.find(".input-group").addClass("opacity-50");
    }

    const deleteButtonContainer = banClone.find(".col-12.col-md-1");
    deleteButtonContainer.html(`
      <button type="button"
              class="btn btn-outline-danger btn-sm delete-ban"
              data-bs-toggle="tooltip"
              data-bs-placement="right"
              data-i18n="tooltip.remove_ban_entry"
              title="${t("tooltip.remove_ban_entry", "Remove this ban entry")}">
        <i class="bx bx-trash bx-xs"></i>
      </button>
    `);

    // Initialize ban scope handlers for the cloned item
    initializeBanScopeHandlers(banClone);

    $("#bans-container").append(banClone);

    // Initialize tooltip for the new delete button
    banClone.find('[data-bs-toggle="tooltip"]').tooltip();
  });

  $("#clear-bans").on("click", function () {
    $("#bans-container")
      .find("li.ban-item")
      .each(function () {
        if ($(this).attr("id") !== "ban-1") {
          $(this).remove();
        }
      });
  });

  $(document).on("click", ".delete-ban", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const banContainer = $(this).closest("li.ban-item");
    if (banContainer.attr("id") === "ban-1") return;
    banContainer.fadeOut(300, function () {
      $(this).remove();
    });
  });

  $("#modal-ban-ips").on("hidden.bs.modal", function () {
    $("#clear-bans").trigger("click");
    const firstBan = $("#ban-1");
    firstBan
      .find("input[name='ip']")
      .val("")
      .removeClass("is-invalid is-valid");
    firstBan.find("input[name='reason']").val("ui");
    firstBan.find(".invalid-feedback").remove();
    originalFlatpickr.setDate(defaultDatetime);
    firstBan.find(".ban-scope-select").val("global").trigger("change");
    // Reset permanent checkbox
    firstBan.find(".permanent-ban-checkbox").prop("checked", false);
    // Re-enable datetime field
    firstBan.find("[type='flatpickr-datetime']").prop("disabled", false);
  });

  // Use ipaddr.js for robust IP validation
  // Use ipaddr.js if available, fallback to a basic check
  const isIp = (v) => {
    if (
      typeof window !== "undefined" &&
      window.ipaddr &&
      window.ipaddr.isValid
    ) {
      try {
        return window.ipaddr.isValid(v);
      } catch (_) {
        return false;
      }
    }
    // Fallback (very permissive minimal check): contains ':' for v6 or 3 dots for v4
    return /:/.test(v) || (v.match(/\./g) || []).length === 3;
  };

  const validateBan = (banIpInput, ipServiceMap) => {
    const value = banIpInput.val().trim();
    let errorMessageKey = "";
    let isValid = true;
    const banContainer = banIpInput.closest("li.ban-item");

    if (value === "") {
      errorMessageKey = "validation.ip_required";
      isValid = false;
    } else if (!isIp(value)) {
      errorMessageKey = "validation.ip_invalid";
      isValid = false;
    } else {
      const banScope = banContainer.find('select[name="ban_scope"]').val();

      if (banScope === "global") {
        if (ipServiceMap.has(`${value}:global`)) {
          errorMessageKey = "validation.ip_global_duplicate";
          isValid = false;
        }
      } else if (banScope === "service") {
        const service = banContainer.find('select[name="service"]').val();
        if (!service) {
          errorMessageKey = "validation.service_required_for_ban";
          isValid = false;
        } else if (ipServiceMap.has(`${value}:service:${service}`)) {
          errorMessageKey = "validation.ip_service_duplicate";
          isValid = false;
        }
      }
    }

    banIpInput
      .toggleClass("is-valid", isValid)
      .toggleClass("is-invalid", !isValid);

    let $feedback = banIpInput.next(".invalid-feedback");
    if (!$feedback.length && !isValid) {
      $feedback = $('<div class="invalid-feedback"></div>').insertAfter(
        banIpInput,
      );
    }

    if (!isValid) {
      const service = banContainer.find('select[name="service"]').val();
      $feedback.text(t(errorMessageKey, { service: service }));
    } else if ($feedback.length) {
      $feedback.text("");
    }

    return isValid;
  };

  $("#bans-container").on("input", "input[name='ip']", function () {
    debounce(() => {
      const $input = $(this);
      const ipServiceMap = new Map();

      $("#bans-container")
        .find("li.ban-item")
        .not($input.closest("li.ban-item"))
        .each(function () {
          const $li = $(this);
          const ip = $li.find("input[name='ip']").val().trim();
          if (!ip) return;

          const banScope = $li.find("select[name='ban_scope']").val();
          if (banScope === "global") {
            ipServiceMap.set(`${ip}:global`, true);
          } else if (banScope === "service") {
            const service = $li.find("select[name='service']").val();
            if (service) ipServiceMap.set(`${ip}:service:${service}`, true);
          }
        });
      validateBan($input, ipServiceMap);
    }, 200)();
  });

  // Handle the permanent ban checkbox change
  $(document).on("change", ".permanent-ban-checkbox", function () {
    const $checkbox = $(this);
    const $banItem = $checkbox.closest("li.ban-item");
    const $datetimeInput = $banItem.find(".flatpickr-input");
    const flatpickrInstance = $datetimeInput[0]._flatpickr;

    if ($checkbox.is(":checked")) {
      // If checked, disable the date/time picker
      if (flatpickrInstance) {
        flatpickrInstance.set("clickOpens", false);
        flatpickrInstance.altInput.disabled = true;
        flatpickrInstance.input.disabled = true;
      }
      $datetimeInput.prop("disabled", true);
      $datetimeInput.parent().addClass("opacity-50");
    } else {
      // If unchecked, enable the date/time picker
      if (flatpickrInstance) {
        flatpickrInstance.set("clickOpens", true);
        flatpickrInstance.altInput.disabled = false;
        flatpickrInstance.input.disabled = false;
      }
      $datetimeInput.prop("disabled", false);
      $datetimeInput.parent().removeClass("opacity-50");
    }
  });

  $("#bans-form").on("submit", function (e) {
    e.preventDefault();
    let allValid = true;
    const ipServiceMap = new Map();

    $("#bans-container")
      .find("li.ban-item")
      .each(function () {
        const $li = $(this);
        const $input = $li.find("input[name='ip']");
        if (!validateBan($input, ipServiceMap)) {
          allValid = false;
        } else {
          const ip = $input.val().trim();
          const banScope = $li.find("select[name='ban_scope']").val();
          if (banScope === "global") {
            ipServiceMap.set(`${ip}:global`, true);
          } else if (banScope === "service") {
            const service = $li.find("select[name='service']").val();
            if (service) ipServiceMap.set(`${ip}:service:${service}`, true);
          }
        }
      });

    if (!allValid) return;

    // Collect valid ban data
    const bans = [];
    $("#bans-container")
      .find("li.ban-item")
      .each(function () {
        const $this = $(this);
        const ip = $this.find("input[name='ip']").val().trim();
        const isPermanent = $this
          .find(".permanent-ban-checkbox")
          .is(":checked");
        const end_date = $this.find(".flatpickr-input").val();
        const reason = $this.find("input[name='reason']").val().trim();
        const ban_scope = $this.find("select[name='ban_scope']").val();
        const service =
          ban_scope === "service"
            ? $this.find("select[name='service']").val()
            : null;

        // Convert end_date to duration in seconds (exp)
        let exp = 0;
        if (!isPermanent && end_date) {
          exp = Math.max(
            0,
            Math.floor(new Date(end_date).getTime() / 1000 - Date.now() / 1000),
          );
        }
        if (isPermanent) {
          exp = 0;
        }

        bans.push({
          ip: ip,
          end_date: isPermanent ? "0" : `${end_date}${getTimeZoneOffset()}`,
          exp: exp,
          reason: reason,
          ban_scope: ban_scope,
          service: service,
        });
      });

    // Create and submit the form
    const form = $("<form>", {
      method: "POST",
      action: `${window.location.pathname}/ban`,
      class: "visually-hidden",
    });
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
        name: "bans",
        value: JSON.stringify(bans),
      }),
    );
    form.appendTo("body").submit();
  });

  // Re-validate IP when service selection changes
  $("#bans-container").on("change", "select[name='service']", function () {
    const $ipInput = $(this).closest("li.ban-item").find("input[name='ip']");
    if ($ipInput.val().trim()) $ipInput.trigger("input");
  });

  // Initialize handlers for the initial ban item
  initializeBanScopeHandlers($("#ban-1"));

  // Function to show/hide service selection based on scope
  function initializeBanScopeHandlers($banItem) {
    const $banScopeSelect = $banItem.find(".ban-scope-select");
    const $serviceField = $banItem.find(".service-field");
    const $serviceSelect = $serviceField.find('select[name="service"]');

    toggleServiceField($banScopeSelect.val(), $serviceField, $serviceSelect); // Initial state

    $banScopeSelect.on("change", function () {
      const newScope = $(this).val();
      toggleServiceField(newScope, $serviceField, $serviceSelect);
      // Re-validate IP on scope change
      const $ipInput = $banItem.find("input[name='ip']");
      if ($ipInput.val().trim())
        setTimeout(() => $ipInput.trigger("input"), 50);
    });
  }

  // Helper to toggle service field visibility and requirement
  function toggleServiceField(scopeValue, $serviceField, $serviceSelect) {
    const showService = scopeValue === "service";
    $serviceField.toggleClass("show", showService); // Use 'show' class for visibility
    if (showService) {
      $serviceSelect.attr("required", true);
    } else {
      $serviceSelect.removeAttr("required");
      $serviceSelect.val(""); // Clear selection when hiding
      // Clear potential validation errors on the service select itself
      $serviceSelect.removeClass("is-invalid");
      const $serviceFeedback = $serviceSelect.next(".invalid-feedback");
      if ($serviceFeedback.length) $serviceFeedback.remove();
    }
  }

  // Event handlers for individual row actions
  $(document).on("click", ".unban-single", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    if (actionLock) return;
    actionLock = true;

    const ip = $(this).data("ip");
    const scope = $(this).data("scope");
    const service = $(this).data("service");

    const ban = {
      ip: ip,
      ban_scope: scope,
      service: service === "_" ? null : service,
      time_remaining: "N/A", // Not needed for unban
    };

    setupUnbanModal([ban]);
    actionLock = false;
  });

  $(document).on("click", ".update-duration-single", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    if (actionLock) return;
    actionLock = true;

    const ip = $(this).data("ip");
    const scope = $(this).data("scope");
    const service = $(this).data("service");
    const isPermanent = $(this).data("permanent");

    const ban = {
      ip: ip,
      ban_scope: scope,
      service: service === "_" ? null : service,
      time_remaining: isPermanent ? "permanent" : "N/A",
    };

    setupUpdateDurationModal([ban]);
    actionLock = false;
  });
});
