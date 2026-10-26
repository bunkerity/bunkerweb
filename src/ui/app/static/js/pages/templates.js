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

    const templateId = $(this).attr("data-template-id");
    setupDeletionModal([templateId]);
    actionLock = false; // Unlock after modal setup
  });

  // Search over the installed templates and the catalogue: each card carries its own lowercase
  // haystack (id, title, description, feature names), so the two sections filter the same way.
  const searchInput = document.getElementById("templates-search");
  const noMatch = document.getElementById("templates-no-match");
  const applySearch = () => {
    const term = (searchInput?.value || "").trim().toLowerCase();
    let visible = 0;
    let total = 0;
    document
      .querySelectorAll(
        "#templates-grid > .col, #templates-catalog-grid > .col",
      )
      .forEach((card) => {
        total += 1;
        const matches = !term || (card.dataset.search || "").includes(term);
        card.hidden = !matches;
        if (matches) visible += 1;
      });
    const headings = [
      document.getElementById("templates-catalog-heading"),
      document.getElementById("templates-catalog-grid"),
    ];
    // A catalogue section with no match would be a bare heading: hide it with its cards.
    const catalogVisible = Array.from(
      document.querySelectorAll("#templates-catalog-grid > .col"),
    ).some((card) => !card.hidden);
    headings.forEach((element) => {
      if (element) element.hidden = Boolean(term) && !catalogVisible;
    });
    if (noMatch) noMatch.hidden = visible > 0 || total === 0;
  };
  searchInput?.addEventListener("input", applySearch);
  document
    .getElementById("templates-search-clear")
    ?.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      applySearch();
    });

  // Feature summary: the badges (and the +N) of a card open every feature of the template,
  // grouped by what supplies it. Read only; the template's own editor holds the settings.
  const featureGroups = [
    ["plugin", () => t("templates.features_plugins", "Plugins")],
    ["config", () => t("templates.features_configs", "Custom configs")],
    ["feature", () => t("templates.features_builtin", "Built-in features")],
  ];
  $(document).on("click", ".template-features-open", function () {
    const card = this.closest("[data-template-id]");
    if (!card) return;
    let features = [];
    try {
      features = JSON.parse(card.dataset.features || "[]");
    } catch (error) {
      features = [];
    }
    document.getElementById("template-features-modal-title").textContent =
      card.dataset.templateTitle || card.dataset.templateId;
    document.getElementById("template-features-open-editor").href =
      card.dataset.templateViewUrl;
    const groups = document.getElementById("template-features-groups");
    groups.replaceChildren();
    featureGroups.forEach(([type, label]) => {
      const items = features.filter((feature) => feature.type === type);
      if (!items.length) return;
      const details = document.createElement("details");
      details.className = "template-feature-group mb-2";
      details.open = true;
      const summary = document.createElement("summary");
      summary.className = "fw-semibold";
      summary.textContent = `${label()} (${items.length})`;
      const list = document.createElement("ul");
      list.className =
        "template-feature-list list-unstyled d-flex flex-wrap gap-1 mt-2 mb-0";
      items.forEach((feature) => {
        const item = document.createElement("li");
        const chip = document.createElement("span");
        chip.className = "tag-chip";
        if (feature.icon) {
          const icon = document.createElement("i");
          icon.className = `bx ${feature.icon}`;
          icon.setAttribute("aria-hidden", "true");
          chip.append(icon);
        }
        chip.append(document.createTextNode(feature.text));
        item.append(chip);
        list.append(item);
      });
      details.append(summary, list);
      groups.append(details);
    });
    new bootstrap.Modal(
      document.getElementById("template-features-modal"),
    ).show(this);
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
        return $(this).attr("data-template-id");
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
