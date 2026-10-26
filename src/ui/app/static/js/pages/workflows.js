/* Workflow list page: client-side filtering and the modals that act on one row.
 *
 * The rows are already rendered server-side; this only wires the row actions to the shared
 * modals and filters what is displayed. Editing the rules themselves lives on the editor
 * page (workflow_editor.js).
 */
(function () {
  "use strict";
  var table;
  var exporting = false;

  function translate(key, fallback, options) {
    return window.i18next
      ? window.i18next.t(
          key,
          Object.assign({ defaultValue: fallback }, options),
        )
      : fallback;
  }

  function readWorkflows() {
    var holder = document.getElementById("workflows-data");
    if (!holder) return [];
    try {
      return JSON.parse(holder.value || "[]");
    } catch (error) {
      return [];
    }
  }

  function byId(workflows) {
    var index = {};
    workflows.forEach(function (flow) {
      index[flow.id] = flow;
    });
    return index;
  }

  function applyFilters(searchInput) {
    var needle = (searchInput ? searchInput.value : "").trim().toLowerCase();
    if (table) table.search(needle).draw();
  }

  function openModal(id) {
    var element = document.getElementById(id);
    if (!element || !window.bootstrap) return;
    window.bootstrap.Modal.getOrCreateInstance(element).show();
  }

  /* The one retained draft (workflow_draft.js): point the Configuration tab at the workflow
     that holds it, show the Unsaved badge, and make opening any other workflow a Save /
     Discard / Cancel decision. */
  function setupDraft(index) {
    var draftApi = window.BWWorkflowDraft;
    var holder = document.getElementById("workflows-data");
    var tabs = document.querySelector("[data-wf-url]");
    if (!draftApi || !tabs) return;
    var workflowsUrl = tabs.dataset.wfUrl;
    var csrfField = document.querySelector('input[name="csrf_token"]');
    var csrf = csrfField ? csrfField.value : "";
    var complete = holder && holder.dataset.truncated !== "yes";

    var record = draftApi.read();
    // A draft whose workflow no longer exists can never be saved; drop it, but only when the
    // list is complete, so a 500-row cut cannot erase a real draft.
    if (record && complete && !index[record.id]) {
      draftApi.clear(record.id);
      record = null;
    }
    var configTab = document.querySelector("[data-wf-config-tab]");
    var viewSelect = document.querySelector("[data-wf-view-select]");
    var target = record
      ? record.id
      : index[draftApi.activeId()]
        ? draftApi.activeId()
        : "";
    if (target) {
      var url = workflowsUrl + "/" + encodeURIComponent(target);
      if (configTab) configTab.setAttribute("href", url);
      if (viewSelect && viewSelect.options.length > 1)
        viewSelect.options[1].value = url;
    }
    draftApi.refreshBadges();

    document.addEventListener(
      "click",
      function (event) {
        var link = event.target.closest && event.target.closest("a[href]");
        if (!link || event.defaultPrevented) return;
        var path = new URL(link.href, window.location.href).pathname;
        var prefix = workflowsUrl + "/";
        if (path.indexOf(prefix) !== 0) return;
        var rest = path.slice(prefix.length);
        // Only an editor URL (/workflows/<id>), never the POST-only action endpoints.
        if (
          !rest ||
          rest.indexOf("/") !== -1 ||
          ["create", "update", "clone", "delete", "attach", "detach"].indexOf(
            rest,
          ) !== -1
        )
          return;
        var targetId = decodeURIComponent(rest);
        var current = draftApi.read();
        if (!current || current.id === targetId) return;
        event.preventDefault();
        draftApi
          .resolveForeign({
            targetId: targetId,
            targetName: index[targetId] ? index[targetId].name : targetId,
            csrf: csrf,
            workflowsUrl: workflowsUrl,
          })
          .then(function (proceed) {
            if (proceed) window.location.assign(link.href);
          });
      },
      true,
    );

    // Deleting the workflow that holds the draft drops the draft with it.
    document.addEventListener("submit", function (event) {
      var form = event.target;
      if (!form.matches || !form.matches('form[action$="/workflows/delete"]'))
        return;
      var idField = form.querySelector('[name="workflow_id"]');
      if (idField) draftApi.clear(idField.value);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var index = byId(readWorkflows());
    var searchInput = document.getElementById("workflows-search");
    var serviceSelect = document.getElementById("workflows-service-filter");
    var attachmentSelect = document.getElementById(
      "workflows-attachment-filter",
    );
    var clearButton = document.getElementById("workflows-search-clear");
    setupDraft(index);

    if (document.getElementById("workflows")) {
      var columns = ":visible:not(:nth-child(-n+2)):not(:last-child)";
      var exportOptions = {
        columns: columns,
        modifier: { search: "applied", selected: null },
        // The services cell shows a count; the export keeps the service names (see the
        // column render below, which answers the "export" data type).
        orthogonal: "export",
      };
      table = initializeDataTable({
        tableSelector: "#workflows",
        tableName: "workflows",
        delegatedTooltips: true,
        dataTableOptions: {
          order: [[2, "asc"]],
          responsive: true,
          columnDefs: [
            { targets: 0, orderable: false, className: "dtr-control" },
            { targets: 1, orderable: false, render: DataTable.render.select() },
            { targets: -1, orderable: false },
            {
              targets: [2, 3],
              render: function (data, type) {
                if (type !== "export") return data;
                var cell = document.createElement("div");
                cell.innerHTML = data;
                // Keep entities encoded for the shared export formatter to decode once.
                return Array.prototype.map
                  .call(cell.children, function (part) {
                    return part.innerHTML.trim();
                  })
                  .join(" ");
              },
            },
            {
              targets: 4,
              render: function (data, type, row, meta) {
                if (type !== "export") return data;
                var node = table && table.row(meta.row).node();
                return node
                  ? (node.dataset.services || "")
                      .split(" ")
                      .filter(Boolean)
                      .join(", ")
                  : data;
              },
            },
          ],
          select: {
            style: "multi+shift",
            selector: "td:nth-child(2)",
            headerCheckbox: "select-page",
          },
          layout: {
            topStart: {
              buttons: [
                {
                  extend: "colvis",
                  columns: [3, 4, 5, 6],
                  text: translate("button.columns", "Columns"),
                },
                {
                  extend: "collection",
                  text: translate("button.export", "Export"),
                  buttons: [
                    {
                      extend: "copy",
                      text: translate("button.copy_visible", "Copy visible"),
                      exportOptions: exportOptions,
                    },
                    {
                      extend: "csv",
                      text: translate("workflows.port.csv", "CSV"),
                      filename: "bw_workflows",
                      bom: true,
                      exportOptions: exportOptions,
                    },
                    {
                      extend: "excel",
                      text: translate("workflows.port.excel", "Excel"),
                      filename: "bw_workflows",
                      exportOptions: exportOptions,
                    },
                    {
                      name: "definitions",
                      text: translate(
                        "workflows.port.export_definitions",
                        "Selected definitions (JSON)",
                      ),
                      enabled: false,
                      action: exportDefinitions,
                    },
                  ],
                },
              ],
            },
            topEnd: null,
            bottomStart: ["pageLength", "info"],
            bottomEnd: "paging",
          },
        },
      });
      var filter = function (settings, data, dataIndex) {
        if (settings.nTable.id !== "workflows") return true;
        var service = serviceSelect ? serviceSelect.value : "";
        var attachment = attachmentSelect ? attachmentSelect.value : "";
        var attached = (table.row(dataIndex).node().dataset.services || "")
          .split(" ")
          .filter(Boolean);
        // WF-22: attachment state first, then the exact-service filter that stays beside it.
        if (attachment === "attached" && !attached.length) return false;
        if (attachment === "none" && attached.length) return false;
        return !service || attached.indexOf(service) !== -1;
      };
      $.fn.dataTable.ext.search.push(filter);
      table.on("destroy.dt", function () {
        var at = $.fn.dataTable.ext.search.indexOf(filter);
        if (at !== -1) $.fn.dataTable.ext.search.splice(at, 1);
      });
      table.on("select.dt deselect.dt", function () {
        table
          .button("definitions:name")
          .enable(!exporting && table.rows({ selected: true }).count() > 0);
      });
      applyFilters(searchInput);
    }

    async function exportDefinitions() {
      if (exporting) return;
      var selected = table
        .rows({ selected: true })
        .nodes()
        .toArray()
        .map(function (row) {
          return row.dataset.workflowId;
        });
      if (!selected.length) return;
      exporting = true;
      var status = document.getElementById("workflows-export-status");
      table.button("definitions:name").enable(false);
      status.textContent = translate(
        "workflows.port.export_loading",
        "Reading selected workflow definitions…",
      );
      try {
        var definitions = Object.create(null);
        var base = window.location.pathname.replace(/\/$/, "");
        for (var id of selected) {
          var response = await fetch(
            base + "/" + encodeURIComponent(id) + "/definition",
            {
              headers: { "X-Requested-With": "XMLHttpRequest" },
              cache: "no-store",
            },
          );
          var result = await response.json();
          if (!response.ok || !result.definition)
            throw new Error(result.message || String(response.status));
          definitions[id] = result.definition;
        }
        var url = URL.createObjectURL(
          new Blob([JSON.stringify(definitions, null, 2)], {
            type: "application/json",
          }),
        );
        var link = document.createElement("a");
        link.href = url;
        link.download = "bw_workflow_definitions.json";
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function () {
          URL.revokeObjectURL(url);
        }, 1000);
        status.textContent = translate(
          "workflows.port.export_done",
          "Selected definitions exported. This file has no re-import contract.",
        );
      } catch (error) {
        status.textContent =
          translate(
            "workflows.port.export_failed",
            "Export failed; no file downloaded.",
          ) +
          " " +
          error.message;
      } finally {
        exporting = false;
        table
          .button("definitions:name")
          .enable(!exporting && table.rows({ selected: true }).count() > 0);
      }
    }

    if (searchInput) {
      searchInput.addEventListener("input", function () {
        applyFilters(searchInput);
      });
    }
    [serviceSelect, attachmentSelect].forEach(function (select) {
      if (select)
        select.addEventListener("change", function () {
          applyFilters(searchInput);
        });
    });
    if (clearButton) {
      clearButton.addEventListener("click", function () {
        if (searchInput) searchInput.value = "";
        applyFilters(searchInput);
      });
    }

    /* WF-22: the attached service names and the detach action. Built from the same JSON the
       page already carries, so an unloaded row (the 500-row cut) never shows a wrong list. */
    function openServices(flow, opener) {
      var list = document.getElementById("workflow-services-list");
      var empty = document.getElementById("workflow-services-empty");
      var form = document.getElementById("workflow-services-detach");
      var title = document.querySelector(
        "#workflow-services-modal .modal-title",
      );
      if (!list || !form) return;
      var services = flow.services || [];
      var readonly = form.dataset.readonly === "yes";
      if (title)
        title.textContent = translate(
          "workflows.port.services_title",
          "Services attached to {{name}}",
          { name: flow.name },
        );
      list.textContent = "";
      services.forEach(function (serviceId) {
        var item = document.createElement("li");
        item.className =
          "list-group-item d-flex align-items-center justify-content-between gap-2";
        var name = document.createElement("span");
        name.className = "svc-code text-break";
        name.textContent = serviceId;
        item.appendChild(name);
        if (!readonly) {
          var button = document.createElement("button");
          button.type = "button";
          button.className = "btn btn-sm btn-outline-danger workflow-detach";
          button.dataset.serviceId = serviceId;
          var label = translate(
            "aria.label.detach_from_service",
            "Detach {{name}} from {{service}}",
            { name: flow.name, service: serviceId },
          );
          button.setAttribute("aria-label", label);
          button.title = label;
          var icon = document.createElement("i");
          icon.className = "bx bx-unlink me-1";
          icon.setAttribute("aria-hidden", "true");
          var text = document.createElement("span");
          text.textContent = translate("service.resources.detach", "Detach");
          button.appendChild(icon);
          button.appendChild(text);
          item.appendChild(button);
        }
        list.appendChild(item);
      });
      list.classList.toggle("d-none", !services.length);
      if (empty) empty.classList.toggle("d-none", services.length > 0);
      document.getElementById("workflow-services-id").value = flow.id;
      document.getElementById("workflow-services-modal").addEventListener(
        "hidden.bs.modal",
        function () {
          var target =
            opener && opener.isConnected
              ? opener
              : document.querySelector(
                  'tr[data-workflow-id="' +
                    CSS.escape(flow.id) +
                    '"] .workflow-services',
                );
          if (target) target.focus({ preventScroll: true });
        },
        { once: true },
      );
      openModal("workflow-services-modal");
    }

    document.addEventListener("click", function (event) {
      var detach = event.target.closest(".workflow-detach");
      if (detach) {
        var form = document.getElementById("workflow-services-detach");
        document.getElementById("workflow-services-service").value =
          detach.dataset.serviceId;
        form.submit();
        return;
      }
      var open = event.target.closest(".workflow-services");
      if (!open) return;
      var row = open.closest("tr");
      if (row && !row.dataset.workflowId) row = row.previousElementSibling;
      var flow = index[row && row.dataset.workflowId];
      if (flow) openServices(flow, open);
    });

    // Responsive copies action markup into child rows; delegate to keep those controls live.
    document.addEventListener("click", function (event) {
      var action = event.target.closest(
        ".workflow-edit, .workflow-attach, .workflow-clone, .workflow-delete",
      );
      if (!action || action.disabled) return;
      var row = action.closest("tr");
      if (row && !row.dataset.workflowId) row = row.previousElementSibling;
      var workflowId = row && row.dataset.workflowId;
      var flow = index[workflowId];
      if (!flow) return;
      if (action.classList.contains("workflow-edit")) {
        document.getElementById("workflow-edit-id").value = workflowId;
        document.getElementById("workflow-edit-name").value = flow.name || "";
        document.getElementById("workflow-edit-description").value =
          flow.description || "";
        openModal("workflow-edit-modal");
      } else if (action.classList.contains("workflow-attach")) {
        document.getElementById("workflow-attach-id").value = workflowId;
        var picker = document.getElementById("workflow-attach-services");
        Array.prototype.forEach.call(picker.options, function (item) {
          item.selected = (flow.services || []).indexOf(item.value) !== -1;
        });
        openModal("workflow-attach-modal");
      } else if (action.classList.contains("workflow-clone")) {
        document.getElementById("workflow-clone-id").value = workflowId;
        document.getElementById("workflow-clone-name").value =
          flow.name + " (copy)";
        openModal("workflow-clone-modal");
      } else {
        document.getElementById("workflow-delete-id").value = workflowId;
        document.getElementById("workflow-delete-name").textContent = flow.name;
        openModal("workflow-delete-modal");
      }
    });
  });
})();
