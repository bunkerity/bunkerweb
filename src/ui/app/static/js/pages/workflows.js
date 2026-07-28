/* Workflow list page: client-side filtering and the modals that act on one row.
 *
 * The rows are already rendered server-side; this only wires the row actions to the shared
 * modals and filters what is displayed. Editing the rules themselves lives on the editor
 * page (workflow_editor.js).
 */
(function () {
  "use strict";

  function rows() {
    return Array.prototype.slice.call(
      document.querySelectorAll(".workflow-row"),
    );
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

  function applyFilters(searchInput, serviceSelect) {
    var needle = (searchInput ? searchInput.value : "").trim().toLowerCase();
    var service = serviceSelect ? serviceSelect.value : "";
    rows().forEach(function (row) {
      var haystack = row.textContent.toLowerCase();
      var services = (row.dataset.services || "").split(" ");
      var matchesSearch = !needle || haystack.indexOf(needle) !== -1;
      var matchesService = !service || services.indexOf(service) !== -1;
      row.classList.toggle("d-none", !(matchesSearch && matchesService));
    });
  }

  function openModal(id) {
    var element = document.getElementById(id);
    if (!element || !window.bootstrap) return;
    window.bootstrap.Modal.getOrCreateInstance(element).show();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var index = byId(readWorkflows());
    var searchInput = document.getElementById("workflows-search");
    var serviceSelect = document.getElementById("workflows-service-filter");
    var clearButton = document.getElementById("workflows-search-clear");

    if (searchInput) {
      searchInput.addEventListener("input", function () {
        applyFilters(searchInput, serviceSelect);
      });
    }
    if (serviceSelect) {
      serviceSelect.addEventListener("change", function () {
        applyFilters(searchInput, serviceSelect);
      });
    }
    if (clearButton) {
      clearButton.addEventListener("click", function () {
        if (searchInput) searchInput.value = "";
        applyFilters(searchInput, serviceSelect);
      });
    }

    rows().forEach(function (row) {
      var workflowId = row.dataset.workflowId;
      var flow = index[workflowId] || { name: workflowId };

      var attach = row.querySelector(".workflow-attach");
      if (attach) {
        attach.addEventListener("click", function () {
          document.getElementById("workflow-attach-id").value = workflowId;
          // Services the workflow already has are preselected, so the multi-select shows
          // the current state instead of an empty box the operator has to rebuild.
          var picker = document.getElementById("workflow-attach-services");
          var attached = (row.dataset.services || "").split(" ");
          Array.prototype.forEach.call(picker.options, function (item) {
            item.selected = attached.indexOf(item.value) !== -1;
          });
          openModal("workflow-attach-modal");
        });
      }

      var clone = row.querySelector(".workflow-clone");
      if (clone) {
        clone.addEventListener("click", function () {
          document.getElementById("workflow-clone-id").value = workflowId;
          document.getElementById("workflow-clone-name").value =
            flow.name + " (copy)";
          openModal("workflow-clone-modal");
        });
      }

      var remove = row.querySelector(".workflow-delete");
      if (remove) {
        remove.addEventListener("click", function () {
          document.getElementById("workflow-delete-id").value = workflowId;
          document.getElementById("workflow-delete-name").textContent =
            flow.name;
          openModal("workflow-delete-modal");
        });
      }
    });
  });
})();
