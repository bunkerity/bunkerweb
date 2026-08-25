$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback, options) => {
          let translated = fallback || key;
          if (options) {
            for (const optKey in options) {
              translated = translated.replace(`{{${optKey}}}`, options[optKey]);
            }
          }
          return translated;
        };

  const BWSelectedList = window.BWSelectedList;
  let toastNum = 0;
  let actionLock = false;
  const serviceNumber = parseInt($("#services_number").val(), 10) || 0;
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const userReadOnly = $("#user-read-only").val().trim() === "True";
  const importDragArea = $("#services-drag-area");
  const importFileInput = $("#services-import-file");
  const importFileList = $("#services-import-file-list");

  // The row actions used to be rendered server-side for every service: ~4.8 KB of near-identical
  // markup per row, 73% of the page and 2.4 MB of it at 500 services. They are built here on
  // draw instead, so only the rows on the visible page exist. `services.html` passes the four
  // per-row facts as data attributes on the (now empty) cell; everything else is page-level.
  //
  // The markup is deliberately identical to what the template emitted, and every string in it is
  // resolved through `t()` as it is built — the catalog is loaded before this file runs, so there
  // is nothing to wait for and nothing to re-translate. The click handlers are delegated on
  // `document`, so nothing needs rebinding.
  const servicesUrl = ($("#services_url").val() || "/services").replace(
    /\/$/,
    "",
  );
  const templatesUrl = ($("#templates_url").val() || "/templates").replace(
    /\/$/,
    "",
  );
  const escapeAttr = (value) =>
    String(value)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  // The name of a service is also an element id (`#type-<name>`, `#method-<name>`), and a dot is
  // not valid in one. Same substitution the template did.
  const idFor = (name) => String(name).replace(/\./g, "-");

  function renderName(id) {
    const safeId = escapeAttr(id);
    const icon = isReadOnly ? "show" : "edit";
    const key = isReadOnly
      ? "tooltip.link.view_service"
      : "tooltip.link.edit_service";
    return `<a href="${servicesUrl}/${encodeURIComponent(id)}" class="d-flex align-items-center"
       data-bs-toggle="tooltip" data-bs-placement="bottom"
       data-bs-original-title="${escapeAttr(t(key, isReadOnly ? "View Service {{service}}" : "Edit Service {{service}}", { service: id }))}"><i class="bx bx-${icon} bx-xs"></i>&nbsp;${safeId}</a>`;
  }

  function renderType(type, name) {
    const draft = type === "draft";
    // `id` and `data-value` are both load-bearing: this file reads `#type-<name>`'s `data-value`
    // when it filters a bulk conversion, and clones the element into the confirm list.
    return `<span id="type-${escapeAttr(idFor(name))}" data-value="${draft ? "draft" : "online"}"
       class="badge rounded-pill bg-label-${draft ? "secondary" : "primary"} d-inline-flex align-items-center"><i class="bx ${draft ? "bx-file-blank" : "bx-globe"} me-1" aria-hidden="true"></i><span>${escapeAttr(t(draft ? "status.draft" : "status.online", draft ? "Draft" : "Online"))}</span></span>`;
  }

  function renderSecurityMode(mode) {
    const detect = mode === "detect";
    return `<span data-value="${detect ? "detect" : "block"}"
       class="badge rounded-pill bg-label-${detect ? "warning" : "primary"} d-inline-flex align-items-center"><i class="bx ${detect ? "bx-show" : "bx-shield-alt-2"} me-1" aria-hidden="true"></i><span>${escapeAttr(t(detect ? "security_mode.detect" : "security_mode.block", detect ? "Detect" : "Block"))}</span></span>`;
  }

  function renderTemplate(template) {
    if (!template) {
      return `<span data-value="none" class="badge rounded-pill bg-label-secondary">${escapeAttr(t("badge.no_template", "No template"))}</span>`;
    }
    const safe = escapeAttr(template);
    const readOnlyTemplate =
      isReadOnly || ["low", "medium", "high", "ui", "api"].includes(template);
    const icon = readOnlyTemplate ? "show" : "edit";
    return `<a href="${templatesUrl}/${encodeURIComponent(template)}" class="d-flex align-items-center"
       data-bs-toggle="tooltip" data-bs-placement="bottom"
       data-bs-original-title="${escapeAttr(t(readOnlyTemplate ? "tooltip.link.view_template" : "tooltip.link.edit_template", readOnlyTemplate ? "View Template {{template}}" : "Edit Template {{template}}", { template: template }))}"><i class="bx bx-${icon} bx-xs"></i>&nbsp;${safe}</a>`;
  }

  function renderRowActions(row) {
    const id = row.name;
    if (!id) return "";
    const safeId = escapeAttr(id);
    const isDraft = row.type === "draft";
    const safeMethod = escapeAttr(row.method || "");
    const canDelete = row.deletable === true;
    const method = row.method || "";
    const editIcon = isReadOnly ? "show" : "edit";

    // Same precedence as the template it replaced: a readonly *user* outranks a readonly
    // database, which outranks a method that forbids deletion.
    let deleteKey = "tooltip.button.delete_service";
    let deleteOptions = `{"name": "${safeId}"}`;
    if (userReadOnly) {
      deleteKey = "tooltip.disabled_readonly";
    } else if (isReadOnly) {
      deleteKey = "tooltip.disabled_db_readonly";
    } else if (!canDelete) {
      deleteKey = "tooltip.disabled_by_method";
      deleteOptions = `{"method": "${safeMethod}"}`;
    }

    const convertTo = isDraft ? "online" : "draft";
    // A service that listens where the fleet does keeps a bare https://<name> link: the rendered
    // port is not the published one there (the images publish 443:8443), so adding it would break
    // a link that works. `link_port` is only set when the service declared HTTPS ports of its own.
    const linkPort = row.link_port ? `:${escapeAttr(String(row.link_port))}` : "";

    return `
      <div class="row-actions">
        <div${
          isDraft
            ? ` data-bs-toggle="tooltip" data-bs-placement="bottom" data-bs-original-title="${t(
                "tooltip.disabled_draft",
                "Disabled by draft mode",
              )}" data-i18n="tooltip.disabled_draft"`
            : ""
        }>
          <a role="button" class="icon-btn${isDraft ? " disabled" : ""}" href="https://${safeId}${linkPort}"
             data-bs-toggle="tooltip" data-bs-placement="bottom"
             data-bs-original-title="${t("tooltip.link.access_service", "Access service {{name}}", { name: id })}"
             data-i18n="tooltip.link.access_service" data-i18n-options='{"name": "${safeId}"}'
             target="_blank" rel="noreferrer"><i class="bx bx-link-external"></i></a>
        </div>
        <a role="button" class="icon-btn" href="${servicesUrl}/${encodeURIComponent(id)}"
           data-bs-toggle="tooltip" data-bs-placement="bottom"
           data-bs-original-title="${t(
             isReadOnly
               ? "tooltip.link.view_service"
               : "tooltip.link.edit_service",
             isReadOnly
               ? "View service {{service}}"
               : "Edit service {{service}}",
             { service: id },
           )}"
           data-i18n="${isReadOnly ? "tooltip.link.view_service" : "tooltip.link.edit_service"}"
           data-i18n-options='{"service": "${safeId}"}'><i class="bx bx-${editIcon}"></i></a>
        <div${
          isReadOnly
            ? ` data-bs-toggle="tooltip" data-bs-placement="bottom" data-bs-original-title="${t(
                "tooltip.disabled_readonly",
                "Disabled by readonly",
              )}"`
            : ""
        }>
          <a role="button" class="icon-btn${isReadOnly ? " disabled" : ""}"
             href="${servicesUrl}/new?clone=${encodeURIComponent(id)}"
             data-bs-toggle="tooltip" data-bs-placement="bottom"
             data-bs-original-title="${t("tooltip.link.clone_service", "Clone service {{name}}", { name: id })}"
             data-i18n="tooltip.link.clone_service" data-i18n-options='{"name": "${safeId}"}'><i class="bx bx-copy-alt"></i></a>
        </div>
        <div${
          isReadOnly
            ? ` data-bs-toggle="tooltip" data-bs-placement="bottom" data-bs-original-title="${t(
                "tooltip.disabled_readonly",
                "Disabled by readonly",
              )}" data-i18n="tooltip.disabled_readonly"`
            : ""
        }>
          <button type="button" class="icon-btn convert-service${isReadOnly ? " disabled" : ""}"
                  data-service-id="${safeId}" data-value="${convertTo}"
                  data-bs-toggle="tooltip" data-bs-placement="bottom"
                  data-bs-original-title="${t(
                    `tooltip.button.convert_service_to_${convertTo}`,
                    `Convert service {{name}} to ${convertTo}`,
                    { name: id },
                  )}"
                  data-i18n="tooltip.button.convert_service_to_${convertTo}"
                  data-i18n-options='{"name": "${safeId}"}'><i class="bx bx-transfer"></i></button>
        </div>
        <button type="button" class="icon-btn info export-service" data-service-id="${safeId}"
                data-bs-toggle="tooltip" data-bs-placement="bottom"
                data-bs-original-title="${t("tooltip.link.export_service", "Export service {{service}} configuration", { service: id })}"
                data-i18n="tooltip.link.export_service"
                data-i18n-options='{"service": "${safeId}"}'><i class="bx bx-export" aria-hidden="true"></i></button>
        <div data-bs-toggle="tooltip" data-bs-placement="bottom"
             data-bs-original-title="${t(deleteKey, "Delete service {{name}}", { name: id, method: method })}"
             data-i18n="${deleteKey}" data-i18n-options='${deleteOptions}'>
          <button type="button" data-service-id="${safeId}"
                  class="icon-btn danger delete-service${canDelete ? "" : " disabled"}"><i class="bx bx-trash"></i></button>
        </div>
      </div>`;
  }

  // components/selected-list.html "columns" mode -- id_key "name" + hidden_mode
  // "csv" reproduces the old services.join(",") hidden value verbatim.
  const serviceColumns = [
    { key: "name", i18n: "table.header.name", label: "Name", bold: true },
    { key: "type", i18n: "table.header.type", label: "Type", safe: true },
  ];

  // A `serverSide` table only holds the rows it is showing, so DataTables drops a selection the
  // moment the user turns the page — and the bulk actions are exactly the thing someone builds
  // across several pages. Keep the names here instead, with the type the confirm list shows: for
  // a service that is no longer in the DOM there is no badge left to clone.
  const selectedServices = new Map();

  const typeOf = (service) =>
    selectedServices.get(service) ||
    $(`#type-${idFor(service)}`).data("value") ||
    "online";

  // The confirm list's "Type" column. An on-screen row's badge is cloned so it keeps any
  // search-highlight styling; anything off-page is rendered from the remembered type.
  const serviceRows = (services) =>
    services.map((service) => {
      const badge = $(`#type-${idFor(service)}`)
        .clone()
        .removeClass("highlight");
      return {
        name: service,
        type: badge.length
          ? badge[0].outerHTML
          : renderType(typeOf(service), service),
      };
    });

  const setupConversionModal = (services, conversionType = "draft") => {
    BWSelectedList.render("#selected-services-convert", serviceRows(services), {
      entity: "services",
      idKey: "name",
      hiddenMode: "csv",
      columns: serviceColumns,
    });

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
    BWSelectedList.render("#selected-services-delete", serviceRows(services), {
      entity: "services",
      idKey: "name",
      hiddenMode: "csv",
      columns: serviceColumns,
    });

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

  // DataTables' own `csv`/`excel` buttons write what the table holds, and a `serverSide` table
  // holds one page: they would have produced a ten-row file, with no error and no sign that 491
  // services were missing. The endpoint applies the same search, order and pane selections the
  // user is looking at — `getDataTableStateParams` is what forwards them.
  const buildServicesExportUrl = (dt, format) =>
    `${servicesUrl}/export/${format}?${$.param({
      ...getDataTableStateParams(dt),
      csrf_token: $("#csrf_token").val(),
    })}`;

  const layout = {
    top1: {
      searchPanes: {
        viewTotal: true,
        cascadePanes: true,
        collapse: false,
        columns: [3, 4, 5, 6, 7, 8],
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

  if (serviceNumber > 10) {
    const menu = [10, 25, 50, 100];
    if (serviceNumber > 100) menu.push(500);
    if (serviceNumber > 500) menu.push(1000);
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
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>CSV`,
          className: "buttons-csv",
          action: (e, dt) => {
            window.location.href = buildServicesExportUrl(dt, "csv");
          },
        },
        {
          text: `<span class="tf-icons bx bx-table bx-18px me-2"></span>Excel`,
          className: "buttons-excel",
          action: (e, dt) => {
            window.location.href = buildServicesExportUrl(dt, "excel");
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

  // #selected-services-{convert,delete,export} rows + hidden input are
  // auto-cleared by static/js/components/selected-list.js's global
  // hidden.bs.modal listener (targets every [data-selected-host]).
  $("#modal-import-services").on("hidden.bs.modal", function () {
    importFileInput.val("");
    importFileList.empty();
    importDragArea.addClass("border-dashed");
    importDragArea.removeClass("bg-primary text-white");
    importDragArea.find("i").addClass("text-primary");
    $("#services-import-configs-options").addClass("d-none");
    $("#services-import-overwrite-configs").prop("checked", false);
  });

  $("#modal-export-services").on("hidden.bs.modal", function () {
    $("#services-export-include-configs").prop("checked", false);
  });

  $("#services-export-confirm").on("click", function () {
    const $modal = $("#modal-export-services");
    const services = BWSelectedList.getIds("#selected-services-export");
    if (services.length === 0) return;
    const includeConfigs = $("#services-export-include-configs").is(":checked");
    window.open(buildExportUrl(services, includeConfigs), "_blank");
    bootstrap.Modal.getInstance($modal[0]).hide();
  });

  const getSelectedServices = () => Array.from(selectedServices.keys());

  // `select`/`deselect` are the only place the two views of a selection meet: DataTables owns the
  // rows on screen, this map owns the rest.
  $("#services").on("select.dt deselect.dt", function (e, dt, type, indexes) {
    if (type !== "row") return;
    dt.rows(indexes)
      .data()
      .each((row) => {
        if (e.type === "select") {
          selectedServices.set(row.name, row.type);
        } else {
          selectedServices.delete(row.name);
        }
      });
  });

  // "Create service" moved to the page-head band as a real link (#services-create-btn,
  // href="{{ url_for('services.services_service_page', service='new') }}") -- no JS needed.
  // "Import services" moved to the page-head band (#services-import-btn); the action
  // itself is unchanged and reused as-is.
  $("#services-import-btn").on("click", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    importFileInput.val("");
    importFileList.empty();
    const modalInstance = new bootstrap.Modal(
      document.getElementById("modal-import-services"),
    );
    modalInstance.show();
  });

  $.fn.dataTable.ext.buttons.convert_services = {
    action: function (e, dt, node) {
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

      const conversionType = $(node).text().trim().split(" ")[2];
      const services = getSelectedServices();
      if (services.length === 0) {
        actionLock = false;
        return;
      }

      const filteredServices = services.filter(
        (service) => typeOf(service) !== conversionType,
      );

      if (filteredServices.length === 0) {
        const feedbackToast = $("#feedback-toast")
          .clone()
          .attr("id", `feedback-toast-${toastNum++}`)
          .removeClass("d-none");
        feedbackToast
          .find("span")
          .text(t("toast.header.conversion_failed", "Conversion failed"));
        feedbackToast
          .find("div.toast-body")
          .text(
            t(
              "toast.body.selected_items_already_in_state",
              "The selected items are already in the requested state.",
            ),
          );
        feedbackToast.appendTo("#feedback-toast-container").toast("show");
        actionLock = false;
        return;
      }

      setupConversionModal(filteredServices, conversionType);
      actionLock = false;
    },
  };

  const servicesWithConfigs = new Set(
    ($("#services_with_configs").val() || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean),
  );

  const buildExportUrl = (services, includeConfigs) => {
    const baseUrl = `${window.location.origin}${window.location.pathname}`;
    const params = new URLSearchParams({ services: services.join(",") });
    if (includeConfigs) params.set("include_configs", "1");
    return `${baseUrl}/export?${params.toString()}`;
  };

  const openExportModal = (services) => {
    if (!services || services.length === 0) return;
    const hasConfigs = services.some((service) =>
      servicesWithConfigs.has(service),
    );
    if (!hasConfigs) {
      // No attached custom configs — skip the modal and download the .env directly.
      window.open(buildExportUrl(services, false), "_blank");
      return;
    }
    BWSelectedList.render(
      "#selected-services-export",
      services.map((service) => ({ id: service, label: service })),
      { entity: "services", idKey: "id", hiddenMode: "csv" },
    );
    $("#services-export-include-configs").prop("checked", false);
    new bootstrap.Modal(
      document.getElementById("modal-export-services"),
    ).show();
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

      openExportModal(services);
      actionLock = false;
    },
  };

  $(document).on("click", ".export-service", function () {
    const serviceId = $(this).data("service-id");
    if (!serviceId) return;
    openExportModal([String(serviceId)]);
  });

  $.fn.dataTable.ext.buttons.delete_services = {
    text: '<span class="tf-icons bx bx-trash bx-18px me-2"></span>Delete',
    action: function () {
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

      const services = getSelectedServices();
      if (services.length === 0) {
        actionLock = false;
        return;
      }

      setupDeletionModal(services);
      actionLock = false;
    },
  };

  const services_config = {
    tableSelector: "#services",
    tableName: "services",
    columnVisibilityCondition: (column) => column > 2 && column < 9,
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
          // `display` only: the row object must never reach the search index or the sort
          // comparator. Both run on the server now, but a client-side copy of either would still
          // match on fields this column shows no text for.
          render: (data, type, row) =>
            type === "display" ? renderRowActions(row) : "",
        },
        {
          targets: 2,
          render: (data, type) =>
            type === "display" ? renderName(data) : data,
        },
        {
          targets: [7, 8],
          render: function (data, type) {
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
            header: t("searchpane.type", "Type"),
            combiner: "or",
            orderable: false,
          },
          targets: 3,
          render: (data, type, row) =>
            type === "display" ? renderType(data, row.name) : data,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.method", "Method"),
            combiner: "or",
            orderable: false,
          },
          targets: 4,
          // A `<td>` id is not something a renderer can set — a renderer produces cell *content*.
          // `#method-<name>` is a hook into this table, so it needs the one callback DataTables
          // gives for the cell element itself.
          createdCell: function (td, cellData, rowData) {
            td.id = `method-${idFor(rowData.name)}`;
          },
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.security_mode", "Security Mode"),
            combiner: "or",
            orderable: false,
          },
          targets: 5,
          render: (data, type) =>
            type === "display" ? renderSecurityMode(data) : data,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.template", "Template"),
            combiner: "or",
          },
          targets: 6,
          render: (data, type) =>
            type === "display" ? renderTemplate(data) : data,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.created", "Created"),
            combiner: "or",
            orderable: false,
          },
          targets: 7,
        },
        {
          searchPanes: {
            show: true,
            header: t("searchpane.last_update", "Last update"),
            combiner: "or",
            orderable: false,
          },
          targets: 8,
        },
      ],
      order: [[2, "asc"]],
      autoFill: false,
      responsive: true,
      processing: true,
      serverSide: true,
      ajax: {
        url: `${servicesUrl}/fetch`,
        type: "POST",
        data: function (d) {
          d.csrf_token = $("#csrf_token").val();
          return d;
        },
        error: function (jqXHR, textStatus, errorThrown) {
          console.error("DataTables AJAX error:", textStatus, errorThrown);
          $("#services").addClass("d-none");
          $("#services-waiting")
            .removeClass("visually-hidden")
            .addClass("text-danger")
            .text(t("status.error_loading_data", "Couldn't load data"));
        },
      },
      // The `<thead>` stays in the template — it carries the translated headers, their tooltips
      // and the colvis labels. These only name the field each column reads out of a row.
      columns: [
        { data: null, defaultContent: "", orderable: false },
        { data: null, defaultContent: "", orderable: false },
        { data: "name" },
        { data: "type" },
        { data: "method" },
        { data: "security_mode" },
        { data: "template" },
        { data: "creation_date" },
        { data: "last_update" },
        { data: null, defaultContent: "", orderable: false },
      ],
      select: {
        style: "multi+shift",
        selector: "td:nth-child(2)",
        headerCheckbox: "select-page",
      },
      layout: layout,
      // main.js initialises tooltips once over the whole document at load; rows drawn after that
      // — every page change, sort and filter — have to opt in or their buttons are silently
      // title-less.
      drawCallback: function () {
        $("#services tbody [data-bs-toggle='tooltip']").tooltip();
        // Rows arriving from a page change are new DOM: re-check the ones the user had already
        // picked, or turning the page and coming back would look like the selection was dropped.
        const api = this.api();
        api.rows().every(function () {
          if (selectedServices.has(this.data().name)) this.select();
        });
      },
      initComplete: function () {
        const $wrapper = $("#services_wrapper");
        $wrapper.find(".btn-secondary").removeClass("btn-secondary");
        if (isReadOnly) {
          $wrapper
            .find(".dt-buttons")
            .attr(
              "data-bs-original-title",
              userReadOnly
                ? t(
                    "tooltip.disabled_readonly",
                    "Disabled: Read-only mode is active.",
                  )
                : t(
                    "tooltip.disabled_db_readonly",
                    "Disabled: The database is in read-only mode.",
                  ),
            )
            .attr("data-bs-placement", "right")
            .tooltip();
        }
      },
    },
  };

  initializeDataTable(services_config);
  $(document).on("click", ".delete-service", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const service = $(this).data("service-id");
    setupDeletionModal([service]);
  });

  $(document).on("click", ".convert-service", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const service = $(this).data("service-id");
    const conversionType = $(this).data("value");
    setupConversionModal([service], conversionType);
  });

  const validateImportFile = (file) => {
    const fileName = file.name.toLowerCase();
    return (
      fileName.endsWith(".env") ||
      fileName.endsWith(".txt") ||
      fileName.endsWith(".zip")
    );
  };

  const toggleConfigsImportOptions = (file) => {
    const $options = $("#services-import-configs-options");
    if (file && file.name.toLowerCase().endsWith(".zip")) {
      $options.removeClass("d-none");
    } else {
      $options.addClass("d-none");
      $("#services-import-overwrite-configs").prop("checked", false);
    }
  };

  importDragArea.on("click", function () {
    importFileInput.click();
  });

  importDragArea.on("keydown", function (e) {
    if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      importFileInput.click();
    }
  });

  importDragArea.on("dragover", function (e) {
    e.preventDefault();
    importDragArea.removeClass("border-dashed");
    importDragArea.addClass("bg-primary text-white");
    importDragArea.find("i").removeClass("text-primary");
  });

  importDragArea.on("dragleave", function (e) {
    e.preventDefault();
    importDragArea.addClass("border-dashed");
    importDragArea.removeClass("bg-primary text-white");
    importDragArea.find("i").addClass("text-primary");
  });

  importFileInput.on("change", function () {
    const file = this.files && this.files[0];
    importFileList.empty();
    toggleConfigsImportOptions(file);
    if (!file) {
      return;
    }
    if (!validateImportFile(file)) {
      alert(
        t(
          "alert.services_import_invalid_file",
          "Please upload a valid services export file (.env or .zip).",
        ),
      );
      importFileInput.val("");
      toggleConfigsImportOptions(null);
      return;
    }
    const fileSize = (file.size / 1024).toFixed(2);
    importFileList.append(
      `<div class="file-item"><strong>${file.name}</strong> (${fileSize} KB)</div>`,
    );
  });

  importDragArea.on("drop", function (e) {
    e.preventDefault();
    importDragArea.addClass("border-dashed");
    importDragArea.removeClass("bg-primary text-white");
    importDragArea.find("i").addClass("text-primary");
    importFileInput.prop("files", e.originalEvent.dataTransfer.files);
    importFileInput.trigger("change");
  });
});
