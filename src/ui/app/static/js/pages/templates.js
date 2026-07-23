$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback, options) => {
          // Basic fallback supporting simple interpolation
          let translated = fallback || key;
          if (options) {
            for (const optKey in options) {
              translated = translated.replace(`{{${optKey}}}`, options[optKey]);
            }
          }
          return translated;
        };

  var actionLock = false;
  const isReadOnly = $("#is-read-only").val().trim() === "True";

  const setupDeletionModal = (templateIds) => {
    const delete_modal = $("#modal-delete-templates");

    window.BWSelectedList.render(
      "#selected-templates",
      templateIds.map((templateId) => ({ id: templateId })),
      {
        entity: "templates",
        idKey: "id",
        hiddenMode: "csv",
        columns: [
          { key: "id", i18n: "table.header.id", label: "ID", bold: true },
        ],
      },
    );

    // Use plural/singular i18n key for alert
    const alertTextKey =
      templateIds.length > 1
        ? "modal.body.delete_confirmation_alert_plural"
        : "modal.body.delete_confirmation_alert";
    const defaultAlertText = `Are you sure you want to delete the selected template${
      templateIds.length > 1 ? "s" : ""
    }?`;
    delete_modal.find(".alert").text(t(alertTextKey, defaultAlertText));

    const modalTemplate = new bootstrap.Modal(delete_modal[0]);
    modalTemplate.show();
  };

  // Modal cleanup: js/components/selected-list.js clears any
  // [data-selected-host] (the #selected-templates macro output, including its
  // hidden input) on every "hidden.bs.modal" globally, so no page-specific
  // handler is needed here.

  // Single-card delete button (card grid's .delete-template, one per card).
  $(document).on("click", ".delete-template", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    if (actionLock) return; // Prevent overlapping actions
    actionLock = true; // Lock action

    const templateId = $(this).data("template-id");
    setupDeletionModal([templateId]);
    actionLock = false; // Unlock after modal setup
  });

  // -- Bulk selection: "Select" toggle reveals per-card checkboxes, feeding
  // the same #modal-delete-templates + selected-list flow as the single-card
  // delete button above.
  const $selectToggle = $("#templates-select-toggle");
  const $deleteSelected = $("#templates-delete-selected");
  const $selectedCount = $("#templates-selected-count");
  let selecting = false;

  const getSelectedTemplates = () =>
    $(".template-checkbox:checked")
      .map(function () {
        return $(this).data("template-id");
      })
      .get();

  const refreshSelectionState = () => {
    const count = getSelectedTemplates().length;
    $deleteSelected.prop("disabled", count === 0);
    $selectedCount.toggleClass("d-none", count === 0).text(count);
  };

  $selectToggle.on("click", function () {
    selecting = !selecting;
    $(".template-select-check").toggleClass("d-none", !selecting);
    $deleteSelected.toggleClass("d-none", !selecting);
    if (!selecting) {
      $(".template-checkbox").prop("checked", false);
    }
    refreshSelectionState();
    $(this)
      .find("span[data-i18n]")
      .attr(
        "data-i18n",
        selecting ? "button.cancel" : "templates.gallery.select",
      )
      .text(
        selecting
          ? t("button.cancel", "Cancel")
          : t("templates.gallery.select", "Select"),
      );
  });

  $(document).on("change", ".template-checkbox", refreshSelectionState);

  $deleteSelected.on("click", function () {
    if (actionLock) return;
    actionLock = true;

    const templateIds = getSelectedTemplates();
    if (templateIds.length === 0) {
      actionLock = false;
      return;
    }
    setupDeletionModal(templateIds);
    actionLock = false;
  });
});
