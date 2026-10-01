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

    // Use plural/singular i18n key for alert. Not the shared `delete_confirmation_alert(_plural)`
    // (M25): that key is hard-coded to say "instance", which was never wrong on `/instances` but
    // is wrong everywhere else it got reused -- including here.
    const alertTextKey =
      templateIds.length > 1
        ? "modal.body.confirm_templates_deletion_alert_plural"
        : "modal.body.confirm_templates_deletion_alert";
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

  // Catalogue install. The endpoint is @cors_required and answers JSON, like /templates/create,
  // so this posts with the XHR header rather than submitting a form. The button is only
  // rendered when the server already decided the item is installable; the route re-checks
  // everything anyway, so a disabled or missing button is a hint and never the control.
  $(document).on("click", ".templates-catalog-install", async function () {
    const button = this;
    const templateId = button.dataset.templateId;
    if (!templateId || button.disabled) return;
    button.disabled = true;

    const body = new FormData();
    body.append("id", templateId);
    const token = document.querySelector("#csrf_token");
    if (token) body.append("csrf_token", token.value);

    try {
      const response = await fetch("/templates/catalog/install", {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        body,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          payload.message ||
            t("plugins.catalog.install_failed", "Install failed"),
        );
      window.location.reload();
    } catch (err) {
      button.disabled = false;
      // eslint-disable-next-line no-alert
      alert(err.message);
    }
  });

  // Template import. JSON in, JSON out (the route is @cors_required), so a refusal -- a bad id,
  // an archive path outside its one folder, an oversized file, an existing id without "replace"
  // -- lands in the modal's own alert and the modal stays open with the file still chosen.
  const postModalForm = async (form, $error, submit, fallback) => {
    $error.addClass("d-none").text("");
    if (submit) submit.disabled = true;

    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        body: new FormData(form),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.message || fallback);
      window.location.reload();
    } catch (err) {
      $error.text(err.message).removeClass("d-none");
      if (submit) submit.disabled = false;
    }
  };

  $("#template-import-form").on("submit", function (event) {
    event.preventDefault();
    postModalForm(
      this,
      $("#template-import-error"),
      document.querySelector("#template-import-submit"),
      t("templates.import.failed", "The template could not be imported."),
    );
  });

  // Catalogue update (C4): the same JSON round trip, from the diff preview's own modal. A refusal
  // -- the listing or the template changed since the preview, a managed template, a name clash --
  // stays in that modal.
  $(".template-catalog-update-form").on("submit", function (event) {
    event.preventDefault();
    postModalForm(
      this,
      $(this).find(".template-catalog-update-error"),
      this.querySelector("button[type=submit]"),
      t(
        "templates.catalog.update_failed",
        "The template could not be updated.",
      ),
    );
  });

  $("#modal-import-template").on("hidden.bs.modal", function () {
    $("#template-import-error").addClass("d-none").text("");
  });

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
