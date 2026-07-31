// Settings widget behaviour for pages that render settings WITHOUT the multi-plugin
// pane/mode chrome: the per-plugin page (plugin_settings_page.html) and the per-service
// template page. It carries the widget bucket -- multiple-group add/remove, reset-to-
// default/global, file settings, multivalue chips, multiselect dropdowns, live regex
// feedback -- plus the normalisation a NATIVE form submit needs (the deleted monolith
// submitted through a synthetic form instead, so those pages never needed it).
//
// It began as a DELIBERATE DUPLICATE of code in plugins-settings.js, not deduplicated
// because every one of these handlers is `$(document).on(...)` delegated and selector-based:
// a page loading both files would double-fire all of them (a single click on `.add-multiple`
// would clone the group twice).
//
//   /services/<svc>/plugins/<id>, /global-settings/plugins/<id>, template page
//                                                -> settings-widgets.js
//
// DONE as of S3.4 T8: the duplicate died with `plugins-settings.js`, so this file is the only
// copy. `/services/<svc>` and `/global-settings` no longer render a settings grid at all --
// they load `js/pages/settings-raw.js`, which shares zero delegated selectors with this file
// (pinned by test_template_settings_page.py::
// test_the_raw_editor_and_the_widgets_module_share_no_delegated_selector).
//
// Deliberate deltas from the copied source (kept as the record of what was changed on the
// way out of the monolith, since the original is no longer there to diff against):
//   1. `.add-multiple` is delegated here; the monolith bound it directly, which
//      covers no group added after DOM-ready. Hygiene rather than a live-bug fix -- the
//      clones this handler makes never carry an ADD button of their own (see the note at
//      the handler) -- but the direct binding is wrong in principle, so it does not
//      survive the copy.
//   2. The multiselect/multivalue init loops became idempotent initMultiselects(root) /
//      initMultivalues(root) guarded by `data-bw-init`, and run on freshly cloned groups
//      too. Without that a multiselect inside a cloned `multiple` group is fully inert
//      (no bootstrap.Dropdown instance, so it never even closes), and a cloned multivalue
//      starts unsynced -- no initial hidden-input write, no has-value classes, no >5
//      collapse -- though typing in it still syncs via the delegated input handler.
//      reverseproxy alone declares 19 `multiple` settings.
//   3. The native-submit normalisation folded in from the deleted
//      js/pages/plugin-settings-page.js, plus a new ace-editor pass.
//
// `ace` is NEVER referenced at module top level (nor anywhere else) -- the monolith's
// top-level `const AceRange = ace.require(...)` is exactly why loading it on a
// page without ace silently killed every statement below it (the rule survives it:
// js/pages/settings-raw.js inherited that line, so its host pages must load ace first).
// Ace content still reaches the
// POST: the submit handler reads the editor's `data-source` mirror textarea instead.
//
// Deps, all loaded by base.html before {% block scripts %}: jQuery (:183), the Bootstrap
// bundle (:185, after jQuery so the jQuery plugin bridge is registered -- `.tooltip()` /
// `.collapse()` are used), `debounce` from js/common.js (:196), i18next + js/i18n.js
// (:200-206). Read-only state is server-rendered as `disabled` attributes; no client-side
// readonly gate is added here and none should be. (One inherited exception, copied as-is:
// `resetInputField` clears `disabled` on every field of a clone -- unreachable on a
// readonly page, where the ADD button itself is disabled, but it does re-enable a
// PRO-locked or scheduler-managed field inside a cloned group. Pre-existing; not fixed
// here.)
$(document).ready(() => {
  // Ensure i18next is loaded before using it
  const t = typeof i18next !== "undefined" ? i18next.t : (key) => key; // Fallback

  // Escapes a string so it can be safely embedded as an HTML attribute value
  function escapeAttr(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  const pendingFileReads = new Set();

  const getValidationTargetInput = ($input) => {
    if ($input.hasClass("plugin-setting-file-text")) {
      const manualSelector = $input.data("manualTarget");
      if (manualSelector) {
        const $manual = $(manualSelector).first();
        if ($manual.length && !$manual.hasClass("d-none")) return $manual;
      }

      const targetSelector = $input.data("uploadTarget");
      if (targetSelector) {
        const $target = $(targetSelector);
        if ($target.length) return $target;
      }
      const $fallback = $input
        .closest(".plugin-file-setting-wrapper")
        .find(".plugin-setting-file-upload")
        .first();
      if ($fallback.length) return $fallback;
    }
    return $input;
  };

  const upsertValidationFeedback = ($target) => {
    let $feedback = $target.next(".invalid-feedback");
    if (!$feedback.length) {
      $feedback = $('<div class="invalid-feedback"></div>').insertAfter(
        $target,
      );
    }
    return $feedback;
  };

  const setFieldValidationState = ($input, isValid, errorMessage = "") => {
    const $target = getValidationTargetInput($input);
    const isFileSetting = $input.hasClass("plugin-setting-file-text");
    $target.toggleClass("is-invalid", !isValid);
    $input.toggleClass("is-invalid", !isValid);
    if (isFileSetting) {
      // Keep file controls neutral on success (no green "is-valid" state).
      $target.removeClass("is-valid");
      $input.removeClass("is-valid");
    }
    const $existingFeedback = $target.next(".invalid-feedback");
    if (!isValid || $existingFeedback.length) {
      const $feedback = $existingFeedback.length
        ? $existingFeedback
        : upsertValidationFeedback($target);
      $feedback.text(isValid ? "" : errorMessage);
    }
    return $target;
  };

  const buildValidationRegex = ($input, pattern) => {
    if ($input.hasClass("plugin-setting-file-text")) {
      // File settings often contain multiline payloads (PEM/base64 blocks).
      return new RegExp(pattern, "s");
    }
    return new RegExp(pattern);
  };

  const FILE_NAME_STORAGE_PREFIX = "bw-file-setting-name::";

  const getFileNameStorageKey = ($fileTextInput) => {
    const settingName = String(
      $fileTextInput.attr("name") || $fileTextInput.attr("id") || "",
    ).trim();
    if (!settingName) return "";
    return `${FILE_NAME_STORAGE_PREFIX}${window.location.pathname}::${settingName}`;
  };

  const getStoredFileSettingName = ($fileTextInput) => {
    const key = getFileNameStorageKey($fileTextInput);
    if (!key || typeof localStorage === "undefined") return "";
    try {
      return String(localStorage.getItem(key) || "");
    } catch (_err) {
      return "";
    }
  };

  const setStoredFileSettingName = ($fileTextInput, fileName) => {
    const key = getFileNameStorageKey($fileTextInput);
    if (!key || typeof localStorage === "undefined") return;
    try {
      const normalizedName = String(fileName || "").trim();
      if (normalizedName) {
        localStorage.setItem(key, normalizedName);
      } else {
        localStorage.removeItem(key);
      }
    } catch (_err) {
      // Ignore storage errors (private mode/quota).
    }
  };

  const clearStoredFileSettingName = ($fileTextInput) => {
    $fileTextInput.removeData("lastFileName");
    $fileTextInput.attr("data-file-name", "");
    setStoredFileSettingName($fileTextInput, "");
  };

  const setCurrentFileSettingName = ($fileTextInput, fileName) => {
    const normalizedName = String(fileName || "").trim();
    if (!normalizedName) {
      clearStoredFileSettingName($fileTextInput);
      return "";
    }
    $fileTextInput.data("lastFileName", normalizedName);
    $fileTextInput.attr("data-file-name", normalizedName);
    setStoredFileSettingName($fileTextInput, normalizedName);
    return normalizedName;
  };

  const syncPersistedFileNameDisplay = ($fileTextInput) => {
    const $wrapper = $fileTextInput.closest(".plugin-file-setting-wrapper");
    const $uploadInput = $wrapper.find(".plugin-setting-file-upload").first();
    const $display = $wrapper
      .find(".plugin-setting-file-upload-display")
      .first();
    if (!$uploadInput.length || !$display.length) return;

    const uploadEl = $uploadInput.get(0);
    const hasSelectedFile = Boolean(
      uploadEl && uploadEl.files && uploadEl.files.length > 0,
    );
    const currentMode = String($fileTextInput.data("inputMode") || "upload");
    const hasContent = String($fileTextInput.val() ?? "").trim() !== "";
    const rememberedFileName =
      String($fileTextInput.data("lastFileName") || "").trim() ||
      String($fileTextInput.attr("data-file-name") || "").trim() ||
      getStoredFileSettingName($fileTextInput);

    if (
      currentMode === "manual" ||
      $uploadInput.hasClass("d-none") ||
      hasSelectedFile ||
      !hasContent ||
      !rememberedFileName
    ) {
      $uploadInput.removeClass("has-persisted-name");
      $display.addClass("d-none").text("");
      return;
    }

    $uploadInput.addClass("has-persisted-name");
    $display.text(rememberedFileName).removeClass("d-none");
  };

  const setFileSettingStatus = ($fileTextInput, textOverride = null) => {
    const $wrapper = $fileTextInput.closest(".plugin-file-setting-wrapper");
    const $status = $wrapper.find(".plugin-setting-file-status").first();
    if (!$status.length) return;

    const rawValue = $fileTextInput.val();
    const value =
      rawValue === undefined || rawValue === null ? "" : String(rawValue);
    if (textOverride !== null) {
      $status.text(textOverride);
      syncPersistedFileNameDisplay($fileTextInput);
      return;
    }

    if (value.trim() === "") {
      clearStoredFileSettingName($fileTextInput);
      const emptyText = $status.data("emptyText") || "No file selected";
      $status.text(emptyText);
      syncPersistedFileNameDisplay($fileTextInput);
      return;
    }

    const rememberedFileName =
      String($fileTextInput.data("lastFileName") || "").trim() ||
      String($fileTextInput.attr("data-file-name") || "").trim() ||
      getStoredFileSettingName($fileTextInput);
    if (rememberedFileName) {
      setCurrentFileSettingName($fileTextInput, rememberedFileName);
      $status.text(
        `Current content loaded from ${rememberedFileName} (${value.length} chars)`,
      );
      syncPersistedFileNameDisplay($fileTextInput);
      return;
    }

    $status.text(`Current content loaded (${value.length} chars)`);
    syncPersistedFileNameDisplay($fileTextInput);
  };

  const syncFileSettingManualInput = ($fileTextInput) => {
    const manualSelector = $fileTextInput.data("manualTarget");
    if (!manualSelector) return $();
    const $manualInput = $(manualSelector).first();
    if (!$manualInput.length) return $();

    const value = String($fileTextInput.val() ?? "");
    if ($manualInput.val() !== value) {
      $manualInput.val(value);
    }
    return $manualInput;
  };

  const setFileSettingMode = ($fileTextInput, mode = "upload") => {
    const $wrapper = $fileTextInput.closest(".plugin-file-setting-wrapper");
    if (!$wrapper.length) return;

    const manualSelector = $fileTextInput.data("manualTarget");
    const uploadSelector = $fileTextInput.data("uploadTarget");
    const $manualInput = manualSelector ? $(manualSelector).first() : $();
    const $uploadInput = uploadSelector ? $(uploadSelector).first() : $();
    const $toggle = $wrapper.find(".plugin-setting-file-mode-toggle").first();
    const $toggleIcon = $toggle.find("i").first();
    const $toggleGroup = $toggle.parent();

    const isManual = mode === "manual";
    $uploadInput.toggleClass("d-none", isManual);
    $manualInput.toggleClass("d-none", !isManual);
    $fileTextInput.data("inputMode", isManual ? "manual" : "upload");

    if ($toggleGroup.length) {
      if (isManual) {
        $toggleGroup
          .removeClass("input-group")
          .addClass("d-flex justify-content-end");
        $toggle.addClass("btn-sm");
      } else {
        $toggleGroup
          .removeClass("d-flex justify-content-end")
          .addClass("input-group");
        $toggle.removeClass("btn-sm");
      }
    }

    if ($toggle.length) {
      const uploadLabel =
        $toggle.data("uploadLabel") || "Switch to text editor";
      const manualLabel = $toggle.data("manualLabel") || "Back to file upload";
      const nextLabel = isManual ? manualLabel : uploadLabel;
      $toggle.attr("data-mode", isManual ? "manual" : "upload");
      $toggle.attr("aria-pressed", isManual ? "true" : "false");
      $toggle.addClass("btn-outline-secondary").removeClass("btn-secondary");
      if (isManual) {
        $toggleIcon.removeClass("bx-edit-alt").addClass("bx-upload");
        $toggle.attr("title", nextLabel);
        $toggle.attr("aria-label", nextLabel);
        $toggle.attr("data-bs-original-title", nextLabel);
      } else {
        $toggleIcon.removeClass("bx-upload").addClass("bx-edit-alt");
        $toggle.attr("title", nextLabel);
        $toggle.attr("aria-label", nextLabel);
        $toggle.attr("data-bs-original-title", nextLabel);
      }

      const toggleEl = $toggle.get(0);
      if (toggleEl && typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
        const tooltipInstance = bootstrap.Tooltip.getInstance(toggleEl);
        if (tooltipInstance) {
          tooltipInstance.hide();
          tooltipInstance.dispose();
          new bootstrap.Tooltip(toggleEl);
        }
      }
    }

    syncPersistedFileNameDisplay($fileTextInput);
  };

  const readFileAsText = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (event) => resolve(String(event.target?.result ?? ""));
      reader.onerror = () =>
        reject(new Error("Unable to read the selected file."));
      reader.readAsText(file);
    });

  const trackPendingFileRead = (promise) => {
    pendingFileReads.add(promise);
    const cleanup = () => pendingFileReads.delete(promise);
    promise.then(cleanup, cleanup);
    return promise;
  };

  const waitForPendingFileReads = async () => {
    if (pendingFileReads.size === 0) return;
    await Promise.allSettled(Array.from(pendingFileReads));
  };

  const highlightSettings = (matchedSettings, fadeTimeout = 800) => {
    matchedSettings.each(function () {
      const $setting = $(this);
      $setting.removeClass("setting-highlight setting-highlight-fade");

      // Check if the setting is inside a collapsed multiple setting group
      const $collapseContainer = $setting.closest(".multiple-collapse");

      if ($collapseContainer.length && !$collapseContainer.hasClass("show")) {
        // Expand the multiple setting group if it's collapsed
        const toggleButton = $(
          `[data-bs-target="#${$collapseContainer.attr("id")}"]`,
        );
        toggleButton.trigger("click");
      }

      // Apply the highlight class
      $setting.addClass("setting-highlight");

      // Remove the highlight after a delay
      setTimeout(() => {
        $setting.addClass("setting-highlight-fade");
      }, fadeTimeout); // Keep highlight for 600 milliseconds

      // Fully remove the highlight after the transition
      setTimeout(() => {
        $setting.removeClass("setting-highlight setting-highlight-fade");
      }, fadeTimeout * 2); // Adjust to match the fade transition time
    });

    // Scroll to the first matched setting smoothly
    if (matchedSettings.length > 0) {
      matchedSettings[0].scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  };

  $(document).on("input", ".plugin-setting", function () {
    debounce(() => {
      const $input = $(this);
      const pattern = $input.attr("pattern");
      let isValid = true;
      if (pattern) {
        try {
          isValid = buildValidationRegex($input, pattern).test($input.val());
        } catch (_err) {
          isValid = false;
        }
      }
      const $target = getValidationTargetInput($input);
      if ($input.hasClass("plugin-setting-file-text")) {
        $target.removeClass("is-valid").toggleClass("is-invalid", !isValid);
        $input.removeClass("is-valid").toggleClass("is-invalid", !isValid);
      } else {
        $target
          .toggleClass("is-valid", isValid)
          .toggleClass("is-invalid", !isValid);
        $input.toggleClass("is-invalid", !isValid);
      }
    }, 100)();
  });

  $(document).on("focusout", ".plugin-setting", function () {
    $(this).removeClass("is-valid");
  });

  $(document).on("click", ".show-multiple", function () {
    const currentTextKey =
      $(this).text().trim() === t("button.multiple_show")
        ? "button.multiple_hide"
        : "button.multiple_show";
    const iconClass =
      currentTextKey === "button.multiple_show" ? "hide" : "show-alt";
    $(this).html(
      `<i class="bx bx-${iconClass} bx-sm"></i>&nbsp;<span data-i18n="${currentTextKey}">${t(
        currentTextKey,
      )}</span>`,
    );
  });

  // DELEGATED -- the monolith binds this directly at :1717, which covers no group added
  // after DOM-ready. No live bug follows from that today: plugin_settings_body.html:146
  // renders ADD only for suffix 0, and this handler strips it from the clone below, so a
  // clone never has an ADD button to be dead. Delegated anyway, because the direct form
  // breaks the moment any group is rendered after ready.
  $(document).on("click", ".add-multiple", function () {
    const multipleId = $(this).attr("id").replace("add-", "");

    // Get all existing suffixes
    const existingContainers = $(`#${multipleId}`).find(".multiple-container");
    const existingSuffixes = existingContainers
      .map(function () {
        return parseInt(
          $(this)
            .find(".multiple-collapse")
            .attr("id")
            .replace(`${multipleId}-`, ""),
        );
      })
      .get()
      .sort((a, b) => a - b); // Sort the suffixes in ascending order

    // Find the first missing suffix
    let suffix = 0;
    for (let i = 0; i < existingSuffixes.length; i++) {
      if (existingSuffixes[i] !== i) {
        suffix = i;
        break;
      }
      suffix = existingSuffixes.length; // If no gaps, use the next number
    }

    const cloneId = `${multipleId}-${suffix}`;

    // Clone the first .multiple-container and reset input values
    const multipleClone = $(`#${multipleId}`)
      .find(".multiple-container")
      .first()
      .clone();

    // Helper function to reset inputs/selects
    const resetInputField = (element, suffix) => {
      const elementType = element.attr("type");
      // Read the raw attribute, NOT .data(): jQuery 4's dataAttr coerces
      // "1.1" -> 1.1, "0"/"false"/"null" -> falsy and "{...}"/"[...]" -> JSON.
      // A coerced number made the select branch's `===` below never match (it
      // compares against option values, which are always strings), deselecting
      // every option so the browser silently fell back to option 0 -- e.g. a
      // cloned REVERSE_PROXY_HTTP_VERSION came out "1.0" instead of "1.1". The
      // old `|| ""` then swallowed the falsy coercions on top, for every type.
      const defaultVal = element.attr("data-default") ?? "";

      // Safeguard checks for missing attributes
      const originalId = element.attr("id") || "";
      const originalLabelledBy = element.attr("aria-labelledby") || "";
      const originalName = element.attr("name");
      const originalFileInputTarget = element.attr("data-file-input") || "";
      const originalUploadTarget = element.attr("data-upload-target") || "";
      const originalManualTarget = element.attr("data-manual-target") || "";

      // Update IDs and attributes
      const newId = originalId.replace("-0", `-${suffix}`);
      const newLabelledBy = originalLabelledBy.replace("-0", `-${suffix}`);
      const newName = originalName ? `${originalName}_${suffix}` : "";
      const newFileInputTarget = originalFileInputTarget.replace(
        "-0",
        `-${suffix}`,
      );
      const newUploadTarget = originalUploadTarget.replace("-0", `-${suffix}`);
      const newManualTarget = originalManualTarget.replace("-0", `-${suffix}`);

      element
        .attr("id", newId)
        .attr("aria-labelledby", newLabelledBy)
        .attr("data-original", defaultVal)
        .prop("disabled", false);

      if (originalFileInputTarget) {
        element.attr("data-file-input", newFileInputTarget);
      }
      if (originalUploadTarget) {
        element.attr("data-upload-target", newUploadTarget);
      }
      if (originalManualTarget) {
        element.attr("data-manual-target", newManualTarget);
      }

      if (originalName) {
        element.attr("name", newName);
      } else {
        element.removeAttr("name");
      }

      if (element.hasClass("plugin-setting-file-manual")) {
        element.val(defaultVal);
        return;
      }

      // Cache label and description elements to avoid multiple traversals
      const settingLabel = element.next("label");
      const labelText = (settingLabel.text() || "").trim();
      const descriptionLabel = settingLabel
        .closest(".col-12")
        .find("label")
        .first();

      // Update label attributes safely
      const originalLabelId = descriptionLabel.attr("id") || "";
      const newLabelId = originalLabelId.replace("-0", `-${suffix}`);
      const originalLabelFor = descriptionLabel.attr("for") || "";
      const newLabelFor = originalLabelFor.replace("-0", `-${suffix}`);

      descriptionLabel.attr("id", newLabelId).attr("for", newLabelFor);
      settingLabel.attr("for", newId).text(`${labelText}_${suffix}`);

      // Reset the value
      if (element.is("select")) {
        element.val(defaultVal);
        element.find("option").each(function () {
          $(this).prop("selected", $(this).val() === defaultVal);
        });
      } else if (elementType === "checkbox") {
        element.prop("checked", defaultVal === "yes");
      } else {
        element.val(defaultVal);
      }

      if (element.hasClass("plugin-setting-file-text")) {
        element.data("fileReadError", false);
        setCurrentFileSettingName(element, "");
        setFieldValidationState(element, true, "");
      }
    };

    // Reset input/select/textarea fields inside the clone
    multipleClone.find("input, select, textarea").each(function () {
      resetInputField($(this), suffix);
    });
    multipleClone.find(".plugin-setting-file-text").each(function () {
      syncFileSettingManualInput($(this));
      setFileSettingMode($(this), "upload");
      setFileSettingStatus($(this));
    });
    multipleClone.find(".plugin-setting-file-mode-toggle").each(function () {
      const currentTarget = $(this).attr("data-file-input") || "";
      $(this).attr(
        "data-file-input",
        currentTarget.replace("-0", `-${suffix}`),
      );
    });

    // Update the collapse section's ID and remove tooltips
    multipleClone.find(".multiple-collapse").attr("id", `${cloneId}`);
    multipleClone
      .find('[data-bs-toggle="tooltip"]:not(.badge)')
      .removeAttr("data-bs-toggle data-bs-placement data-bs-original-title");

    // Update the title with the new suffix
    const multipleTitle = multipleClone.find("h6");
    const titleText = multipleTitle.text().replace(/#\d+$/, ""); // Remove existing suffix if present
    multipleTitle.text(`${titleText} #${suffix}`);

    // Remove "add-multiple" button and append the "REMOVE" button
    multipleClone.find(".add-multiple").remove();
    const multipleShow = multipleClone.find(".show-multiple");
    multipleShow.before(`
      <div>
        <button id="remove-${cloneId}" type="button" class="btn btn-xs btn-text-danger rounded-pill remove-multiple p-0 pe-2">
          <i class="bx bx-trash bx-sm"></i>&nbsp;<span data-i18n="button.multiple_remove">${t(
            "button.multiple_remove",
          )}</span>
        </button>
      </div>
    `);

    multipleShow.html(
      `<i class="bx bx-hide bx-sm"></i>&nbsp;<span data-i18n="button.multiple_show">${t(
        "button.multiple_show",
      )}</span>`,
    );
    multipleClone.find(".multiple-collapse").collapse("hide");

    // Insert the new element in the correct order based on suffix
    let inserted = false;
    existingContainers.each(function () {
      const containerSuffix = parseInt(
        $(this)
          .find(".multiple-collapse")
          .attr("id")
          .replace(`${multipleId}-`, ""),
      );
      if (containerSuffix > suffix) {
        $(this).before(multipleClone); // Insert before the first container with a higher suffix
        inserted = true;
        return false; // Break the loop
      }
    });

    if (!inserted) {
      // If no higher suffix was found, append to the end
      $(`#${multipleId}`).append(multipleClone);
    }

    // Reinitialize Bootstrap tooltips for the newly added clone
    multipleClone.find('[data-bs-toggle="tooltip"]').tooltip();

    // Update show-multiple button's target and aria-controls attributes
    const showMultiple = multipleClone.find(".show-multiple");
    showMultiple
      .attr("data-bs-target", `#${cloneId}`)
      .attr("aria-controls", cloneId);

    // The multivalue/multiselect widgets inside the clone are NOT wired by the
    // delegated handlers alone -- they need their per-container init (hidden-input
    // sync, bootstrap Dropdown, search/selected-only bindings). The clone was taken
    // from an already-initialised container, so it also carries its data-bw-init
    // markers: strip them first or the guarded init below no-ops on it.
    multipleClone.find("[data-bw-init]").removeAttr("data-bw-init");
    // The clone inherited the source group's chip rows and resetInputField
    // blanked each one, so a group with one filled value cloned to two empty
    // rows. Rebuild from the (already reset) hidden input instead: the
    // default's chips plus exactly one trailing empty row.
    multipleClone.find(".multivalue-container").each(function () {
      const $container = $(this);
      rebuildMultivalueRows(
        $container,
        $container.find(".multivalue-hidden-input").val(),
      );
    });
    initMultivalues(multipleClone);
    initMultiselects(multipleClone);

    setTimeout(() => {
      showMultiple.trigger("click");
      highlightSettings(multipleClone);
    }, 30);
  });

  $(document).on("click", ".remove-multiple", function () {
    const multipleId = $(this).attr("id").replace("remove-", "");
    const multiple = $(`#${multipleId}`);

    // Check if any input/select is disabled, and exit early if so
    let disabled = false;
    multiple.find("input, select").each(function () {
      if ($(this).prop("disabled")) {
        disabled = true;
        return false; // Exit the loop early
      }
    });

    if (disabled) return;

    const elementToRemove = multiple.parent();

    // Ensure the element has the 'collapse' class
    if (!elementToRemove.hasClass("collapse")) {
      elementToRemove.addClass("collapse show");
    }

    // Initialize Bootstrap Collapse for the element
    const bsCollapse = new bootstrap.Collapse(elementToRemove, {
      toggle: false, // Ensure we only collapse, not toggle
    });

    // Start the collapsing animation and adjust padding
    bsCollapse.hide();
    elementToRemove.removeClass("pt-2 pb-2").addClass("pt-0 pb-0");

    // Remove the element after collapse transition completes
    elementToRemove.on("hidden.bs.collapse", function () {
      setTimeout(() => {
        $(this).remove(); // Remove the element after collapse
      }, 60);
    });
  });

  // Reset setting handler
  $(document).on("click", ".reset-setting", function (e) {
    e.preventDefault();
    e.stopPropagation();

    // Find the associated input/select/checkbox/multivalue
    const $settingField = $(this).closest("div").find(".plugin-setting");
    const settingType = $settingField.attr("type");
    const isGlobal = $(this).attr("data-bs-original-title").includes("global");

    // Get default or global value depending on the button tooltip
    const valueToSet = isGlobal
      ? $settingField.data("original")
      : $settingField.data("default");

    // Apply the value based on field type
    if ($settingField.is("select")) {
      $settingField.find("option").each(function () {
        $(this).prop("selected", $(this).val() === valueToSet);
      });
      $settingField.val(valueToSet).trigger("change");
    } else if (settingType === "checkbox") {
      $settingField.prop("checked", valueToSet === "yes").trigger("change");
    } else if ($settingField.hasClass("plugin-setting-file-text")) {
      $settingField.data("fileReadError", false);
      $settingField.val(valueToSet).trigger("input").trigger("change");
      const fileNameToSet = String(
        isGlobal
          ? $settingField.data("originalFileName")
          : $settingField.data("defaultFileName") || "",
      ).trim();
      setCurrentFileSettingName($settingField, fileNameToSet);
      const $uploadInput = $settingField
        .closest(".plugin-file-setting-wrapper")
        .find(".plugin-setting-file-upload")
        .first();
      if ($uploadInput.length) {
        $uploadInput.val("").removeClass("is-valid is-invalid");
      }
      setFieldValidationState($settingField, true, "");
      syncFileSettingManualInput($settingField);
      setFileSettingStatus($settingField);
    } else if ($settingField.hasClass("multivalue-hidden-input")) {
      // Handle multivalue reset
      rebuildMultivalueRows(
        $settingField.closest(".multivalue-container"),
        valueToSet,
      );
    } else if (
      $settingField.closest(".dropdown").find(".multiselect-toggle").length
    ) {
      $settingField.val(valueToSet).trigger("input");
      const $dropdown = $settingField.closest(".dropdown");
      const separator = $dropdown.data("separator");
      const separatorValue = separator === undefined ? " " : String(separator);
      const selectedValues = valueToSet
        ? separatorValue === ""
          ? valueToSet.split("")
          : valueToSet.split(separatorValue)
        : [];

      $dropdown.find(".form-check-input").each(function () {
        const $checkbox = $(this);
        const checkboxVal = $checkbox.val();
        $checkbox.prop("checked", selectedValues.includes(checkboxVal));
      });
      updateMultiselectDisplay($dropdown);
    } else {
      $settingField.val(valueToSet).trigger("input");
    }

    // Highlight the field to indicate it's been reset
    const $setting = $settingField.closest(".col-12");
    highlightSettings($setting);
  });

  $(".plugin-setting-file-text").each(function () {
    const $fileTextInput = $(this);
    const persistedFileName = String(
      $fileTextInput.attr("data-file-name") || "",
    ).trim();
    if (persistedFileName) {
      setCurrentFileSettingName($fileTextInput, persistedFileName);
    } else {
      clearStoredFileSettingName($fileTextInput);
    }
    syncFileSettingManualInput($fileTextInput);
    setFileSettingMode($fileTextInput, "upload");
    setFileSettingStatus($fileTextInput);
  });

  $(document).on("click", ".plugin-setting-file-mode-toggle", function () {
    const $toggle = $(this);
    const hiddenInputSelector = $toggle.data("fileInput");
    const $fileTextInput = hiddenInputSelector
      ? $(hiddenInputSelector).first()
      : $toggle
          .closest(".plugin-file-setting-wrapper")
          .find(".plugin-setting-file-text")
          .first();

    if (!$fileTextInput.length) return;

    const currentMode = String($toggle.attr("data-mode") || "upload");
    const nextMode = currentMode === "manual" ? "upload" : "manual";
    setFileSettingMode($fileTextInput, nextMode);
    if (nextMode === "manual") {
      const $manualInput = syncFileSettingManualInput($fileTextInput);
      if ($manualInput.length) {
        $manualInput.trigger("focus");
      }
    }
  });

  $(document).on("input", ".plugin-setting-file-manual", function () {
    const $manualInput = $(this);
    const hiddenInputSelector = $manualInput.data("fileInput");
    const $fileTextInput = hiddenInputSelector
      ? $(hiddenInputSelector).first()
      : $manualInput
          .closest(".plugin-file-setting-wrapper")
          .find(".plugin-setting-file-text")
          .first();

    if (!$fileTextInput.length) return;

    const normalizedContent = String($manualInput.val() ?? "")
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n");
    if ($manualInput.val() !== normalizedContent) {
      $manualInput.val(normalizedContent);
    }
    $fileTextInput.data("fileReadError", false);
    clearStoredFileSettingName($fileTextInput);
    $fileTextInput.val(normalizedContent).trigger("input").trigger("change");
    setFileSettingStatus($fileTextInput);
  });

  $(document).on("change", ".plugin-setting-file-upload", function () {
    const $uploadInput = $(this);
    const hiddenInputSelector = $uploadInput.data("fileInput");
    const $fileTextInput = hiddenInputSelector
      ? $(hiddenInputSelector).first()
      : $uploadInput
          .closest(".plugin-file-setting-wrapper")
          .find(".plugin-setting-file-text")
          .first();

    if (!$fileTextInput.length) return;

    const file = this.files && this.files[0];
    if (!file) {
      $fileTextInput.data("fileReadError", false);
      setFieldValidationState($fileTextInput, true, "");
      syncFileSettingManualInput($fileTextInput);
      setFileSettingStatus($fileTextInput);
      return;
    }

    const pendingRead = readFileAsText(file)
      .then((content) => {
        const normalizedContent = content
          .replace(/\r\n/g, "\n")
          .replace(/\r/g, "\n");
        $fileTextInput.data("fileReadError", false);
        setCurrentFileSettingName($fileTextInput, file.name);
        $fileTextInput
          .val(normalizedContent)
          .trigger("input")
          .trigger("change");
        setFieldValidationState($fileTextInput, true, "");
        syncFileSettingManualInput($fileTextInput);
        setFileSettingStatus(
          $fileTextInput,
          `Loaded: ${file.name} (${normalizedContent.length} chars)`,
        );
      })
      .catch(() => {
        $fileTextInput.data("fileReadError", true);
        setFieldValidationState(
          $fileTextInput,
          false,
          "Unable to read the selected file.",
        );
        setFileSettingStatus($fileTextInput, `Unable to read: ${file.name}`);
        // Clear on failure so the same file can be selected again immediately.
        $uploadInput.val("");
      });

    trackPendingFileRead(pendingRead);
  });

  // Multivalue functionality -- chip/tag rows (type + Enter adds a chip,
  // click the x removes one; see models/multivalue_setting.html for the
  // markup + why). Rows are plain divs now, no per-row <label> (that
  // duplicated the field's own name -- the including settings loop
  // renders one label above this whole field), so updateMultivalueLabels
  // only has ids left to resync after an add/remove shifts indices.
  const updateMultivalueLabels = ($container) => {
    const $hiddenInput = $container.find(".multivalue-hidden-input");
    const baseId = $hiddenInput.attr("id");

    $container.find(".multivalue-input-group").each(function (index) {
      $(this)
        .find(".multivalue-input")
        .attr("id", `${baseId}_${index + 1}`);
    });
  };

  // Toggles ".has-value", which the chip CSS keys its filled/empty look and
  // remove-button visibility off. Named for its earlier form-floating-label
  // duty; kept as-is since it still does exactly what its callers need.
  const updateMultivalueFloatingLabel = ($container) => {
    $container.find(".multivalue-input-group").each(function () {
      const $inputGroup = $(this);
      const $input = $inputGroup.find(".multivalue-input");
      const inputValue = $input.val() || "";
      const hasValue = inputValue.trim() !== "";

      if (hasValue) {
        $inputGroup.addClass("has-value");
      } else {
        $inputGroup.removeClass("has-value");
      }
    });
  };

  const seeMoreLabel = t("link.see_more", { defaultValue: "See more" });
  const showLessLabel = t("plugins.multivalue.show_less", {
    defaultValue: "Show less",
  });
  const moreValueLabel = t("plugins.multivalue.more_value", {
    defaultValue: "more value",
  });
  const moreValuesLabel = t("plugins.multivalue.more_values", {
    defaultValue: "more values",
  });
  const multivalueEnterPlaceholder = t("placeholder.multivalue_enter_value", {
    defaultValue: "Enter value...",
  });
  const multivalueRemoveLabel = t("aria.label.remove_value", {
    defaultValue: "Remove value",
  });

  const toggleMultivalueVisibility = ($container, isToggleAction = false) => {
    const $inputGroups = $container.find(".multivalue-input-group");
    const visibleLimit = 5;

    if ($inputGroups.length <= visibleLimit) {
      $container.find(".multivalue-toggle").remove();
      $inputGroups.show();
      return;
    }

    let $toggle = $container.find(".multivalue-toggle");
    if (!$toggle.length) {
      const toggleHtml = `
        <div class="multivalue-toggle mt-2 mb-2">
          <button type="button" class="btn btn-sm btn-outline-secondary multivalue-toggle-btn" aria-expanded="false">
            <i class="bx bx-chevron-down me-1"></i>
            <span class="toggle-text"></span>
          </button>
        </div>
      `;
      $container.find(".multivalue-inputs").after(toggleHtml);
      $toggle = $container.find(".multivalue-toggle");
    }

    const $toggleBtn = $toggle.find(".multivalue-toggle-btn");
    const $toggleText = $toggle.find(".toggle-text");
    const hiddenCount = Math.max($inputGroups.length - visibleLimit, 0);
    let isExpanded = $toggleBtn.hasClass("expanded");

    if (isToggleAction) {
      isExpanded = !isExpanded;
      $toggleBtn.toggleClass("expanded", isExpanded);
    }

    if (isExpanded) {
      $inputGroups.show();
      $toggleText.text(showLessLabel);
      $toggleBtn.attr("aria-expanded", "true");
    } else {
      $inputGroups.show();
      $inputGroups.slice(visibleLimit).hide();
      const moreLabel = hiddenCount === 1 ? moreValueLabel : moreValuesLabel;
      $toggleText.html(
        `${seeMoreLabel} (<span class="hidden-count">${hiddenCount}</span> ${moreLabel})`,
      );
      $toggleBtn.attr("aria-expanded", "false");
    }
  };

  const updateMultivalueHiddenInput = ($container) => {
    const separator = $container.data("separator") || " ";
    const $hiddenInput = $container.find(".multivalue-hidden-input");
    const values = [];

    $container.find(".multivalue-input").each(function () {
      const value = ($(this).val() || "").trim();
      if (value) {
        values.push(value);
      }
    });

    $hiddenInput.val(values.join(separator));
    $hiddenInput.trigger("change");
  };

  // Builds one chip row: a borderless text input plus (unless disabled) an
  // inline x button. Shared by addMultivalueItem (single row) and
  // rebuildMultivalueRows (full rebuild) so both stay in sync instead of
  // hand-rolling their own copy of the markup.
  const buildMultivalueChip = (id, value, disabled) => {
    const $inputGroup = $("<div>", { class: "multivalue-input-group" });
    const $input = $("<input>", {
      type: "text",
      class: "form-control form-control-sm multivalue-input",
      id,
      placeholder: multivalueEnterPlaceholder,
    });
    $input.val(value);
    if (disabled) $input.prop("disabled", true);
    $inputGroup.append($input);

    if (!disabled) {
      $inputGroup.append(
        `<button type="button"
                class="multivalue-chip-remove remove-multivalue-item"
                aria-label="${escapeAttr(multivalueRemoveLabel)}">
            <i class="bx bx-x" aria-hidden="true"></i>
          </button>`,
      );
    }
    return $inputGroup;
  };

  const addMultivalueItem = ($container, value = "", $insertAfter = null) => {
    const $hiddenInput = $container.find(".multivalue-hidden-input");
    if ($hiddenInput.prop("disabled")) return;

    const baseId = $hiddenInput.attr("id");
    const currentCount = $container.find(".multivalue-input-group").length;
    const $inputGroup = buildMultivalueChip(
      `${baseId}_${currentCount + 1}`,
      value,
      false,
    );

    if ($insertAfter && $insertAfter.length) {
      $insertAfter.after($inputGroup);
    } else {
      $container.find(".multivalue-inputs").append($inputGroup);
    }

    // Renumber ids -- insertAfter can land this row mid-list, not just last
    updateMultivalueLabels($container);
    $inputGroup.find(".multivalue-input").focus();
    updateMultivalueFloatingLabel($container);
    updateMultivalueHiddenInput($container);
    toggleMultivalueVisibility($container, false);

    const numItemsAfter = $container.find(".multivalue-input-group").length;
    if (numItemsAfter > 5) {
      const $toggleBtn = $container.find(".multivalue-toggle-btn");
      if ($toggleBtn.length && !$toggleBtn.hasClass("expanded")) {
        toggleMultivalueVisibility($container, true);
      }
    }
  };

  // Keeps exactly one empty trailing chip available to type into.
  // addMultivalueItem/the Enter handler below already preserve this
  // invariant when THEY add a row; this covers the resource-group-picker
  // path, which fills a row's value directly instead of going through
  // addMultivalueItem.
  const ensureMultivalueTrailingSlot = ($container) => {
    const $hiddenInput = $container.find(".multivalue-hidden-input");
    if ($hiddenInput.prop("disabled")) return;
    const $groups = $container.find(".multivalue-input-group");
    const lastValue = (
      $groups.last().find(".multivalue-input").val() || ""
    ).trim();
    if ($groups.length === 0 || lastValue !== "") {
      addMultivalueItem($container, "");
    }
  };

  // Rebuilds every chip row of a multivalue field from a raw separator-joined
  // string, padding a trailing empty slot -- shared by reset-to-default,
  // apply-template and fetch-global-config so they stay in sync with
  // addMultivalueItem's markup instead of each hand-rolling its own.
  const rebuildMultivalueRows = ($container, rawValue) => {
    const separator = $container.data("separator") || " ";
    const $hiddenInput = $container.find(".multivalue-hidden-input");
    const disabled = $hiddenInput.prop("disabled");
    const baseId = $hiddenInput.attr("id");
    let values = (rawValue ? rawValue.split(separator) : [""]).map((v) =>
      v.trim(),
    );
    if (!disabled && values[values.length - 1] !== "") {
      values = values.concat([""]);
    }

    $container.find(".multivalue-input-group").remove();
    $container.find(".multivalue-toggle").remove();

    const $inputsContainer = $container.find(".multivalue-inputs");
    values.forEach((value, index) => {
      $inputsContainer.append(
        buildMultivalueChip(`${baseId}_${index + 1}`, value, disabled),
      );
    });

    updateMultivalueHiddenInput($container);
    updateMultivalueFloatingLabel($container);
    toggleMultivalueVisibility($container, false);
  };

  const removeMultivalueItem = ($inputGroup, $container) => {
    if ($container.find(".multivalue-input-group").length <= 1) {
      $inputGroup.find(".multivalue-input").val("");
      updateMultivalueHiddenInput($container);
      updateMultivalueFloatingLabel($container);
      return;
    }

    const wasExpanded = $container
      .find(".multivalue-toggle-btn")
      .hasClass("expanded");

    $inputGroup.remove();

    updateMultivalueLabels($container);
    updateMultivalueHiddenInput($container);
    updateMultivalueFloatingLabel($container);
    toggleMultivalueVisibility($container, false);

    if (wasExpanded) {
      const $toggleBtn = $container.find(".multivalue-toggle-btn");
      if ($toggleBtn.length && !$toggleBtn.hasClass("expanded")) {
        toggleMultivalueVisibility($container, true);
      }
    }
  };

  // Initialize multivalue containers under `root` (the monolith runs this once as a
  // bare `.each()` at ready). Idempotent: the data-bw-init marker means a re-run --
  // on a cloned `multiple` group, say -- can neither skip a fresh container nor
  // re-process one that is already wired.
  const initMultivalues = (root) => {
    $(root)
      .find(".multivalue-container")
      .each(function () {
        if (this.dataset.bwInit === "multivalue") return;
        this.dataset.bwInit = "multivalue";
        const $container = $(this);
        updateMultivalueHiddenInput($container);
        updateMultivalueFloatingLabel($container);
        toggleMultivalueVisibility($container, false);
      });
  };

  // Handle multivalue toggle button clicks
  $(document).on("click", ".multivalue-toggle-btn", function () {
    const $container = $(this).closest(".multivalue-container");
    toggleMultivalueVisibility($container, true);
  });

  // Handle remove (x) button clicks -- the only add gesture left is typing +
  // Enter in the trailing empty chip (see the keydown handler below), so
  // there's no more "add" button/handler to wire up here.
  $(document).on("click", ".remove-multivalue-item", function () {
    const $inputGroup = $(this).closest(".multivalue-input-group");
    const $container = $(this).closest(".multivalue-container");
    removeMultivalueItem($inputGroup, $container);
  });

  // Handle input changes
  $(document).on("input", ".multivalue-input", function () {
    const $container = $(this).closest(".multivalue-container");
    updateMultivalueHiddenInput($container);
    updateMultivalueFloatingLabel($container);
  });

  // Insert compatible resource groups as canonical @alias values. The
  // generator expands them by setting kind; literal values remain untouched.
  $(document).on("change", ".resource-group-picker", function () {
    const token = String($(this).val() || "").trim();
    if (!token) return;

    const $hiddenInput = $($(this).data("target"));
    const $container = $hiddenInput.closest(".multivalue-container");
    const exists = $container
      .find(".multivalue-input")
      .toArray()
      .some((input) => String($(input).val() || "").trim() === token);

    if (!exists) {
      const $emptyInput = $container
        .find(".multivalue-input")
        .filter(function () {
          return String($(this).val() || "").trim() === "";
        })
        .first();
      if ($emptyInput.length) {
        $emptyInput.val(token);
        updateMultivalueHiddenInput($container);
        updateMultivalueFloatingLabel($container);
      } else {
        addMultivalueItem($container, token);
      }
      ensureMultivalueTrailingSlot($container);
    }

    $(this).val("");
  });

  // Handle focus/blur for chip focus styling
  $(document).on("focus blur", ".multivalue-input", function () {
    const $container = $(this).closest(".multivalue-container");
    updateMultivalueFloatingLabel($container);
  });

  // Handle Enter key in multivalue inputs: commits the current chip and
  // opens a fresh empty one right after it (type-and-press-enter-to-add).
  $(document).on("keydown", ".multivalue-input", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      const $container = $(this).closest(".multivalue-container");
      const $currentInputGroup = $(this).closest(".multivalue-input-group");
      const currentValue = ($(this).val() || "").trim();

      if (currentValue) {
        addMultivalueItem($container, "", $currentInputGroup);
      }
    }
  });

  // Rebuild the removable-chip row + linked "view selected" modal body that
  // models/multiselect_setting.html renders when it opts into
  // `multiselect_chips`. Fast no-op (two empty-selector lookups) for every
  // other multiselect -- those don't render [data-multiselect-chips] or a
  // linked "[data-multiselect-target]" modal body, so both come back empty.
  const renderMultiselectChips = ($dropdown) => {
    const $chipsRow = $dropdown.find("[data-multiselect-chips]");
    const dropdownId = $dropdown.attr("id");
    const $modalBody = dropdownId
      ? $(`[data-multiselect-target="#${dropdownId}"]`)
      : $();
    if (!$chipsRow.length && !$modalBody.length) return;

    const selected = $dropdown
      .find('.multiselect-options input[type="checkbox"]:checked')
      .map(function () {
        // Read raw attributes, not jQuery .data() -- it coerces numeric-looking
        // values (e.g. bad-behavior's "400"/"401" status-code option ids) and
        // caches the first read, silently corrupting them on later lookups.
        return {
          value: String(this.getAttribute("value") ?? ""),
          label: String(this.getAttribute("data-label") ?? this.value ?? ""),
        };
      })
      .get();

    const chipHtml = (item) =>
      `<span class="badge rounded-pill bg-label-secondary d-inline-flex align-items-center gap-1 multiselect-chip" data-chip-value="${escapeAttr(item.value)}">` +
      `<span class="multiselect-chip-label">${escapeAttr(item.label)}</span>` +
      `<button type="button" class="btn-close multiselect-chip-remove" data-remove-value="${escapeAttr(item.value)}" aria-label="Remove ${escapeAttr(item.label)}"></button>` +
      `</span>`;

    if ($chipsRow.length) {
      $chipsRow
        .toggleClass("d-none", selected.length === 0)
        .html(selected.map(chipHtml).join(""));
    }

    $dropdown
      .find(".multiselect-eye")
      .toggleClass("d-none", selected.length === 0);

    if ($modalBody.length) {
      $modalBody
        .find("[data-multiselect-selected-list]")
        .html(selected.map(chipHtml).join(""));
      $modalBody
        .find(".multiselect-selected-empty")
        .toggleClass("d-none", selected.length > 0);
    }
  };

  // Handle removing a selected option from either the trigger-chips row or
  // the linked "view selected" modal -- both share the same
  // .multiselect-chip-remove markup (models/multiselect_setting.html).
  // Unchecking + triggering "change" reuses the existing checkbox-change
  // handler below (updates the hidden input, badge, footer count and, via
  // renderMultiselectChips, both chip surfaces) instead of duplicating that
  // bookkeeping here.
  $(document).on("click", ".multiselect-chip-remove", function (e) {
    e.preventDefault();
    e.stopPropagation();
    const value = String(this.getAttribute("data-remove-value") ?? "");
    const $dropdown = $(this).closest(".multiselect-container");
    const $scope = $dropdown.length
      ? $dropdown
      : $(
          $(this)
            .closest("[data-multiselect-target]")
            .attr("data-multiselect-target") || "__none__",
        );
    if (!$scope.length) return;
    $scope
      .find('.multiselect-options input[type="checkbox"]')
      .filter(function () {
        return String(this.getAttribute("value")) === value;
      })
      .prop("checked", false)
      .trigger("change");
  });

  // Multiselect dropdown functionality with search
  const updateMultiselectDisplay = ($dropdown) => {
    const $toggle = $dropdown.find(".multiselect-toggle");
    const $badge = $toggle.find("[data-selected-badge]");
    const $countDisplay = $dropdown.find("[data-selected-count]");
    const $checkboxes = $dropdown.find(
      '.multiselect-options input[type="checkbox"]',
    );

    const checkedCheckboxes = $checkboxes.filter(":checked");
    const checkedCount = checkedCheckboxes.length;

    // Update the count in the badge
    if ($badge.length) {
      $badge.text(checkedCount);
    }

    // Update the count in the footer
    if ($countDisplay.length) {
      $countDisplay
        .text(
          t("template.editor.multiselect_summary", {
            count: checkedCount,
            defaultValue: `${checkedCount} selected`,
          }),
        )
        .attr("data-i18n-options", JSON.stringify({ count: checkedCount }));
    }

    // Get separator from dropdown data attribute
    const separator = $dropdown.data("separator");
    const separatorValue =
      separator === undefined || separator === null ? " " : String(separator);

    // Update the hidden value - separated list of selected option IDs
    const selectedIds = checkedCheckboxes
      .map(function () {
        return $(this).attr("value");
      })
      .get();

    // Find or create hidden input to store the value
    let $hiddenInput = $dropdown.find('input[type="hidden"]');
    if ($hiddenInput.length === 0) {
      const settingName = $toggle.find(".multiselect-text").text();
      $hiddenInput = $(
        `<input type="hidden" name="${escapeAttr(settingName)}" class="plugin-setting">`,
      );
      $dropdown.append($hiddenInput);
    }

    // Save as list of option IDs joined by the separator
    $hiddenInput.val(selectedIds.join(separatorValue));

    // Trigger change event for validation
    $hiddenInput.trigger("change");

    // No-op unless this control opted into multiselect_chips (see helper doc).
    renderMultiselectChips($dropdown);
  };

  // Filter multiselect options based on search input and selected-only mode
  const filterMultiselectOptions = ($dropdown, searchTerm, selectedOnly) => {
    const $options = $dropdown.find(".multiselect-option");
    const $noOptionsMsg = $dropdown.find(".no-options-message");
    let visibleCount = 0;

    const lowerTerm = searchTerm.toLowerCase().trim();

    $options.each(function () {
      const $option = $(this);
      const label = $option.text().toLowerCase();
      // data() parses numeric attributes as numbers, so coerce to string first
      const optionId = String($option.data("option-id") ?? "").toLowerCase();
      const isChecked = $option.find('input[type="checkbox"]').is(":checked");

      const matchesSearch =
        label.includes(lowerTerm) || optionId.includes(lowerTerm);
      const matchesFilter = !selectedOnly || isChecked;

      // Use d-none class toggling instead of show()/hide() because
      // the options have d-flex which uses !important and overrides inline display:none
      if ((matchesSearch || !lowerTerm) && matchesFilter) {
        $option.removeClass("d-none");
        visibleCount++;
      } else {
        $option.addClass("d-none");
      }
    });

    // Show/hide no options message
    // Use class toggling instead of show()/hide() because d-none uses !important
    if (visibleCount === 0) {
      $noOptionsMsg.removeClass("d-none");
    } else {
      $noOptionsMsg.addClass("d-none");
    }
  };

  // Helper to re-apply current filters on a dropdown
  const applyMultiselectFilters = ($dropdown) => {
    const searchTerm = $dropdown.find(".multiselect-search").val() || "";
    const selectedOnly =
      $dropdown.find(".multiselect-selected-only-btn").attr("aria-pressed") ===
      "true";
    filterMultiselectOptions($dropdown, searchTerm, selectedOnly);
  };

  // Initialize multiselect dropdowns under `root` with custom behavior (the
  // monolith runs this once as a bare `.each()` at ready). Idempotent: the
  // data-bw-init marker means a re-run -- on a cloned `multiple` group, say --
  // can neither skip a fresh dropdown nor double-bind the per-dropdown search /
  // selected-only handlers, which are direct bindings, not delegated ones.
  const initMultiselects = (root) => {
    $(root)
      .find(".multiselect-container")
      .each(function () {
        if (this.dataset.bwInit === "multiselect") return;
        this.dataset.bwInit = "multiselect";
        const $dropdown = $(this);

        // Sync checkbox states from the hidden input value (or data-default fallback).
        // The template may render with no checkboxes checked when setting_value is
        // None/empty, so we need to initialise from the stored value or the default.
        const $hiddenInput = $dropdown.find('input[type="hidden"]');
        if ($hiddenInput.length) {
          const hiddenVal = $hiddenInput.val();
          // An empty string is a valid multiselect value (no options selected).
          // Only fall back to data-default when the value is truly absent.
          const rawValue =
            hiddenVal != null ? hiddenVal : $hiddenInput.data("default") || "";
          const initValue = String(rawValue);
          if (initValue) {
            const separator = $dropdown.data("separator");
            const sepStr = String(separator ?? "");
            let selectedIds =
              sepStr === "" ? [...initValue] : initValue.split(sepStr);

            // Fallback: if split produced no matching option IDs, try character-by-character.
            // This handles the case where DB separator is NULL but plugin.json intended "".
            if (sepStr !== "") {
              const optionIds = new Set();
              $dropdown
                .find('.multiselect-options input[type="checkbox"]')
                .each(function () {
                  optionIds.add($(this).attr("value"));
                });
              const hasMatch = selectedIds.some((id) => optionIds.has(id));
              if (!hasMatch && initValue.length > 0) {
                selectedIds = [...initValue];
              }
            }

            const selectedSet = new Set(selectedIds);
            $dropdown
              .find('.multiselect-options input[type="checkbox"]')
              .each(function () {
                $(this).prop("checked", selectedSet.has($(this).attr("value")));
              });
          }
        }

        updateMultiselectDisplay($dropdown);

        // Hide search bar if there are 10 or fewer options
        const optionCount = $dropdown.find(".multiselect-option").length;
        if (optionCount <= 10) {
          $dropdown.find(".multiselect-search-container").addClass("d-none");
        }

        // Initialize Bootstrap dropdown
        const $toggle = $dropdown.find(".multiselect-toggle");
        if ($toggle.length) {
          new bootstrap.Dropdown($toggle[0], {
            autoClose: "outside",
            popperConfig: {
              strategy: "fixed",
              modifiers: [
                {
                  name: "preventOverflow",
                  options: {
                    boundary: "viewport",
                    padding: { top: 80 },
                  },
                },
              ],
            },
          });
        }

        // Handle search input
        const $searchInput = $dropdown.find(".multiselect-search");
        if ($searchInput.length) {
          $searchInput.on("input", function () {
            applyMultiselectFilters($dropdown);
          });

          // Prevent dropdown from closing when clicking search input
          $searchInput.on("click", function (e) {
            e.stopPropagation();
          });

          // Prevent Bootstrap Dropdown from capturing keyboard events (arrow keys,
          // Escape) that would steal focus away from the search input
          $searchInput.on("keydown keyup", function (e) {
            e.stopPropagation();
          });
        }

        // Handle "show selected only" toggle
        const $selectedOnlyBtn = $dropdown.find(
          ".multiselect-selected-only-btn",
        );
        if ($selectedOnlyBtn.length) {
          // Dispose any tooltip initialized by main.js global init and reinitialize
          // with a dynamic title function so applyTranslations() updates are picked
          // up on every show (Bootstrap 5 Tooltip lacks setContent unlike Popover).
          const existingTooltip = bootstrap.Tooltip.getInstance(
            $selectedOnlyBtn[0],
          );
          if (existingTooltip) existingTooltip.dispose();
          const selectedOnlyBtnEl = $selectedOnlyBtn[0];
          new bootstrap.Tooltip(selectedOnlyBtnEl, {
            title() {
              return selectedOnlyBtnEl.getAttribute("data-bs-original-title");
            },
          });

          $selectedOnlyBtn.on("click", function (e) {
            e.stopPropagation();
            const isActive = $(this).attr("aria-pressed") === "true";
            $(this).attr("aria-pressed", String(!isActive));
            $(this).toggleClass("active", !isActive);
            applyMultiselectFilters($dropdown);
          });
        }
      });
  };

  // Handle checkbox changes in multiselect dropdowns
  $(document).on(
    "change",
    '.multiselect-container input[type="checkbox"]',
    function () {
      const $dropdown = $(this).closest(".multiselect-container");
      updateMultiselectDisplay($dropdown);
      // Re-apply filters so that unchecking in "selected only" mode hides the option
      applyMultiselectFilters($dropdown);
    },
  );

  // Handle clicking on multiselect options - toggle checkbox
  $(document).on("click", ".multiselect-option", function (e) {
    e.stopPropagation();

    const $checkbox = $(this).find('input[type="checkbox"]');
    // Only manually toggle if clicking directly on checkbox
    // Otherwise, let the native label behavior work
    if ($(e.target).is('input[type="checkbox"]')) {
      $checkbox.trigger("change");
    }
  });

  // Prevent closing dropdown when clicking inside options
  $(document).on("click", ".multiselect-menu", function (e) {
    e.stopPropagation();
  });

  // Prevent Bootstrap Dropdown from capturing keyboard events on any focused
  // element inside the menu (checkboxes, labels). Without this, ArrowDown/Up
  // triggers Bootstrap's focus() loop which can crash the browser tab.
  $(document).on("keydown keyup", ".multiselect-menu", function (e) {
    e.stopPropagation();
  });

  // Close multiselect when clicking outside
  $(document).on("click", function (e) {
    const $target = $(e.target);

    $(".multiselect-container").each(function () {
      const $dropdown = $(this);
      const $toggle = $dropdown.find(".multiselect-toggle");
      const dropdown = bootstrap.Dropdown.getInstance($toggle[0]);

      if (dropdown && !$dropdown.has($target).length && !$target.is($toggle)) {
        dropdown.hide();
      }
    });
  });

  // Registered BEFORE the widget inits below on purpose. `initMultiselects` and the
  // file-setting init loop touch `bootstrap` unguarded, and a throw there would abort the
  // rest of this closure -- structurally the same failure this file's header describes for
  // `ace.require` in the monolith, except the payload here is data destruction, not dead
  // widgets: with no submit listener, unchecked switches post nothing and an omitted
  // in-scope key is DELETED. Losing widget behaviour is survivable; losing settings is not.
  //
  // Native-submit normalisation (folded in from the deleted
  // js/pages/plugin-settings-page.js). These pages post the real <form>; they do not
  // load js/pages/settings-raw.js, whose buildRawForm builds a synthetic form out of the
  // ace editor. Three widget types need normalising first, because for
  // them "absent" and "off" look the same to the browser but mean opposite things to
  // the save: an omitted in-scope key is DELETED (db_methods/config_save.py:592), not
  // left alone.
  //
  // Everything else already posts natively: selects are real <select>s, and
  // multiselect and multivalue widgets keep their value in named hidden inputs.
  const form = document.querySelector("form[data-plugin-settings-form]");
  if (form) {
    let resubmitQueued = false;

    form.addEventListener("submit", (event) => {
      // A file chosen a moment ago may still be mid-FileReader; its content has not
      // landed in the hidden text input yet, so submitting now would save the OLD
      // value. Defer once, then re-submit -- requestSubmit (unlike form.submit())
      // re-fires this listener, which then runs the normalisation below exactly once
      // with an empty pending set. Browsers without requestSubmit just fall through.
      //
      // `resubmitQueued` makes the deferral idempotent: without it a second Save click
      // while the read is still pending queues a SECOND requestSubmit, and because the
      // two land in separate microtasks the browser fires two submit events -- two POSTs,
      // two update_service tasks.
      if (
        pendingFileReads.size > 0 &&
        typeof form.requestSubmit === "function"
      ) {
        event.preventDefault();
        if (resubmitQueued) return;
        resubmitQueued = true;
        waitForPendingFileReads().then(() => {
          resubmitQueued = false;
          form.requestSubmit();
        });
        return;
      }

      // A checked checkbox has no `value` attribute in the markup, so it would natively
      // post "on"; give it "yes" in place so it posts correctly on its own name. An
      // unchecked box posts nothing at all, so it still needs an explicit "no" fallback
      // inserted right after it -- never remove the box's own `name`: doing so used to
      // survive into a bfcache snapshot, permanently leaving a switch that can't
      // re-serialise after a back-button return.
      //
      // Position matters: request.form.to_dict() keeps the FIRST value for a repeated
      // field name, and these pages always emit their own trailing hidden control
      // inputs for control keys like USE_UI after this body. Inserting the fallback
      // right after its own checkbox -- instead of at the end of the form -- keeps it
      // ahead of that trailing hidden input, so a genuine "no" wins instead of being
      // shadowed by a stale "yes" for any control key also declared as a setting.
      form
        .querySelectorAll('input[type="checkbox"].plugin-setting')
        .forEach((box) => {
          if (box.disabled || !box.name) return;
          if (box.checked) {
            box.value = "yes";
            return;
          }
          const explicit = document.createElement("input");
          explicit.type = "hidden";
          explicit.name = box.name;
          explicit.value = "no";
          box.insertAdjacentElement("afterend", explicit);
        });

      // File-type settings carry their filename in a companion key that the
      // multi-plugin JS appends. Without it a filename change is dropped
      // (extract_file_setting_names reads it).
      form
        .querySelectorAll("input.plugin-setting-file-text")
        .forEach((field) => {
          if (!field.name) return;
          const companion = document.createElement("input");
          companion.type = "hidden";
          companion.name = field.name + "__FILE_NAME";
          companion.value = (field.dataset.fileName || "").trim();
          form.appendChild(companion);
        });

      // Ace editors (custom configs) have NO named field of their own: the editor
      // syncs into a `data-source` mirror textarea that carries no `name`, and the only
      // code that ever produced a named field for it was the monolith's getFormFromSettings
      // (deleted in T8; its successor buildRawForm is raw-only) -- so without
      // this the edited config never reaches the POST. Read the mirror, not the `ace`
      // global: this module must load and work with ace undefined. Unchanged content
      // (still equal to the template default) is deliberately not posted, which is what
      // keeps a config that matches its template from being materialised as a real row.
      form.querySelectorAll(".ace-editor").forEach((editorEl) => {
        const name = editorEl.dataset.name;
        const sourceSelector = editorEl.dataset.source;
        if (!name || !sourceSelector) return;
        const mirror = document.querySelector(sourceSelector);
        if (!mirror) return;

        const value = String(mirror.value ?? mirror.textContent ?? "").trim();
        const defaultEl = document.getElementById(`${editorEl.id}-default`);
        const defaultValue = defaultEl
          ? String(defaultEl.value ?? defaultEl.textContent ?? "").trim()
          : "";
        if (value === defaultValue) return;

        const hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = name;
        hidden.value = value;
        form.appendChild(hidden);
      });
    });
  }

  // Consumed by js/pages/template-settings-page.js, which loads AFTER this file on the
  // per-service template page. The stepper it carries -- validateCurrentStepInputs,
  // resetTemplateConfig, the fetch-global handler, all copied from plugins-settings.js --
  // calls these helpers, which live in this closure and are unreachable from another file.
  // Exporting beats copying them a THIRD time: three copies to keep in sync instead of two.
  //
  // Exactly what that file consumes, nothing more. Helpers these call internally
  // (getValidationTargetInput, upsertValidationFeedback, the file-name storage helpers, ...)
  // stay closed over and are deliberately NOT part of the surface.
  //
  // Registered before the inits below for the same reason the submit listener is: a throw in
  // initMultiselects would abort this closure, and the stepper page would then come up with
  // every step navigation and every validation silently dead.
  window.BWSettingsWidgets = Object.freeze({
    t,
    buildValidationRegex,
    setFieldValidationState,
    highlightSettings,
    setCurrentFileSettingName,
    syncFileSettingManualInput,
    setFileSettingStatus,
    rebuildMultivalueRows,
    updateMultiselectDisplay,
  });

  // Last: see the ordering note above the submit listener.
  initMultivalues(document);
  initMultiselects(document);
});
