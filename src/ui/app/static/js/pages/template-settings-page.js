// Stepper behaviour for the per-service template page
// (/services/<svc>/templates/<tpl>, template_settings_page.html).
//
// Extracted from js/plugins-settings.js -- the easy pane's stepper, verbatim except for the
// deviations listed below. The monolith keeps its own copy and is byte-for-byte untouched;
// NO PAGE MAY LOAD BOTH FILES (every handler here and in settings-widgets.js is
// `$(document).on(...)` delegated, so a page loading both would double-fire all of them).
// Removal trigger is the same as settings-widgets.js's: S3.4 retires the advanced pane and
// the monolith's copy dies with it. Until then, fix bugs in BOTH.
//
// Loaded AFTER js/components/settings-widgets.js, which owns the widget bucket
// (multivalue/multiselect/file/validation-feedback) and exports the handful of helpers this
// file's copied bodies call, as `window.BWSettingsWidgets`. That module is a hard dependency:
// without it there is no stepper at all (see the guard below).
//
// What is deliberately NOT here, and why: the mode chrome, the plugin nav, template tabs
// (handleTabChange / showTemplateTab / setCurrentTemplate / updateTemplateUrl / updateUrlParams
// / isInit) -- this page renders exactly one template and no modes; the `.save-settings` click
// hijack and getFormFromSettings -- this page submits its real <form> natively and
// settings-widgets.js normalises that submit; everything raw-mode (AceRange,
// setupRawDisabledHighlight, triggerRawConfigSave, parseRawKeySpec/makeRawKeyPredicates, the
// Ctrl-S handler); and the dead clearStepValidationStyles / validateAllSteps (the latter has
// zero call sites in the monolith).
//
// `ace` is never referenced at closure top level -- `const AceRange = ace.require(...)` at
// plugins-settings.js:2521 is exactly why loading the monolith on a page without ace silently
// kills every statement below it. That alone is NOT enough here: `.ace-editor` always matches
// on this page, so `ace.edit()` in the init loop runs at ready time and a throw there would
// abort this closure just the same. The init loop is therefore registered LAST, after every
// handler -- see the note above it.
//
// Deps beyond settings-widgets.js: jQuery + the Bootstrap bundle + `debounce` (js/common.js),
// all from base.html; ace (libs/ace/src-min/ace.js), which the PAGE must load -- ace-free
// degradation is not a goal here, the page always renders custom-config editors.
$(document).ready(() => {
  // settings-widgets.js runs first (script order + both files use $(document).ready, and
  // deferred scripts execute in document order). Its export carries the widget helpers the
  // copied stepper bodies below call; they live in its closure and are unreachable otherwise.
  // Fail loudly: a missing export would otherwise turn every validation and every step
  // navigation into a silent no-op.
  const W = window.BWSettingsWidgets;
  if (!W) {
    console.error(
      "template-settings-page.js: js/components/settings-widgets.js must load first " +
        "(window.BWSettingsWidgets is missing). Stepper disabled.",
    );
    return;
  }
  const {
    t,
    buildValidationRegex,
    setFieldValidationState,
    highlightSettings,
    setCurrentFileSettingName,
    syncFileSettingManualInput,
    setFileSettingStatus,
    rebuildMultivalueRows,
    updateMultiselectDisplay,
  } = W;

  let toastNum = 0;
  let currentStep = 1;
  const isReadOnlyValue = $("#is-read-only").val() || "";
  const isReadOnly = isReadOnlyValue.trim() === "True";

  const normalizeTemplateId = (value) => {
    if (value === undefined || value === null) return "";
    const raw = value.toString().trim();
    if (!raw) return "";
    const plusNormalized = raw.replace(/\+/g, " ");
    try {
      return decodeURIComponent(plusNormalized);
    } catch (err) {
      return plusNormalized;
    }
  };

  // The service's currently-selected template. The page emits #used-template
  // (value = selected_template, "" when the service uses none); resetTemplateConfig reads it
  // to decide between "restore the saved values" (this IS the active template) and "load this
  // template's defaults" (it is not).
  const $templateInput = $("#used-template");
  let usedTemplate = "low";
  if ($templateInput.length) {
    const normalizedUsedTemplate = normalizeTemplateId($templateInput.val());
    usedTemplate = normalizedUsedTemplate !== "" ? normalizedUsedTemplate : "";
  }

  // DEVIATION 1 -- the page renders exactly one template and no #selected-template input, so
  // the template id comes from the pane markup instead. Every pane carries data-template-id
  // (the outer template pane emitted by the page, and each step pane inside
  // models/template_steps_body.html:107). Qualified with `.tab-pane` to match
  // getTemplateContainer's own selector: getting this wrong is total and silent -- a
  // currentTemplate that no pane carries makes every getTemplateContainer/getStepContainer
  // empty, and the whole stepper no-ops.
  const currentTemplate = normalizeTemplateId(
    $(".tab-pane[data-template-id]").first().attr("data-template-id"),
  );

  const templateDomIdMap = {};
  const domIdToTemplateIdMap = {};
  const assignedDomIds = new Set();

  const sanitizeDomId = (value) => {
    const normalizedValue = normalizeTemplateId(value);
    const sanitized = normalizedValue
      .replace(/[^0-9A-Za-z_-]+/g, "-")
      .replace(/^-+/, "")
      .replace(/-+$/, "");
    return sanitized || "template";
  };

  const registerDomId = (templateId, preferredDomId) => {
    const key = normalizeTemplateId(templateId);
    if (!key) return;

    let baseDomId = sanitizeDomId(preferredDomId || key);
    let domId = baseDomId;
    let suffix = 2;
    while (assignedDomIds.has(domId)) {
      domId = `${baseDomId}-${suffix}`;
      suffix += 1;
    }
    templateDomIdMap[key] = domId;
    domIdToTemplateIdMap[domId] = key;
    assignedDomIds.add(domId);
  };

  // DEVIATION 2 -- the monolith fills this map from #templates-dropdown-menu, which this page
  // does not render. Scan the panes instead: they carry both data-template-id and
  // data-template-dom-id. This matters -- sanitizeDomId(templateId) is NOT guaranteed to equal
  // the server's dom_id, and when it differs getStepContainer returns an empty set and every
  // validation and navigation silently no-ops.
  //
  // The `already registered` guard is NOT cosmetic: N step panes all carry the same pair, and
  // registerDomId's collision loop would hand the 2nd..Nth `<dom_id>-2`, `<dom_id>-3` ... and
  // OVERWRITE templateDomIdMap[key] with the last one -- an id that matches no element. The
  // collision loop exists for two DIFFERENT templates that sanitize to the same id; re-seeing
  // the same template is not that case. The monolith's dropdown emits one button per template
  // so the guard is inert there.
  $(
    "#templates-dropdown-menu button[data-template-id], [data-template-id][data-template-dom-id]",
  ).each(function () {
    const $element = $(this);
    const templateId = normalizeTemplateId($element.data("template-id"));
    if (!templateId || templateDomIdMap[templateId]) return;
    const domId = normalizeTemplateId($element.data("template-dom-id"));
    registerDomId(templateId, domId);
  });

  const getTemplateDomId = (templateId) => {
    const key = normalizeTemplateId(templateId);
    if (!key) return "";
    if (!templateDomIdMap[key]) {
      registerDomId(key);
    }
    return templateDomIdMap[key];
  };

  const getTemplateContainer = (templateId) => {
    const key = normalizeTemplateId(templateId);
    if (!key) return $();
    return $(`.tab-pane[data-template-id="${key}"]`);
  };

  const getStepId = (templateId, step) =>
    `navs-steps-${getTemplateDomId(templateId)}-${step}`;

  const getStepContainer = (templateId, step) =>
    $(`#${getStepId(templateId, step)}`);

  // Helper functions for styling step buttons and navigation
  const stepButtonStyles = {
    // Active states
    activeValid: {
      step: "btn-primary",
      remove: "disabled btn-outline-primary btn-outline-danger btn-danger",
    },
    activeError: {
      step: "btn-danger", // Active step with errors should have btn-danger
      remove: "disabled btn-outline-primary btn-outline-danger btn-primary",
    },
    // Inactive states
    inactiveValid: {
      step: "btn-outline-primary disabled", // Always disabled for inactive
      remove: "btn-primary btn-outline-danger btn-danger",
    },
    inactiveError: {
      step: "btn-outline-danger disabled", // Always disabled for inactive
      remove: "btn-primary btn-outline-primary btn-danger",
    },
  };

  // Text styling for steps
  const textStyles = {
    active: { add: "text-primary", remove: "text-muted" },
    inactive: { add: "text-muted", remove: "text-primary" },
  };

  // Apply button styling based on state
  const applyStepButtonStyle = ($stepItem, styleType) => {
    const style = stepButtonStyles[styleType];
    $stepItem
      .find(".step-number")
      .addClass(style.step)
      .removeClass(style.remove);
  };

  // Apply text styling based on state
  const applyStepTextStyle = ($stepItem, isActive) => {
    const style = isActive ? textStyles.active : textStyles.inactive;
    $stepItem.find(".fw-bold").addClass(style.add).removeClass(style.remove);
  };

  // Set complete styling for a step based on state
  const styleStepNavItem = ($stepItem, isActive, hasError) => {
    // Toggle active/show classes for the list-group-item
    $stepItem.toggleClass("active show", isActive);

    // Set button style based on active state and validation status
    if (isActive) {
      applyStepButtonStyle($stepItem, hasError ? "activeError" : "activeValid");
      // Remove border-danger class - we'll use the button color instead
      $stepItem.find(".step-number").removeClass("border-danger");
    } else {
      applyStepButtonStyle(
        $stepItem,
        hasError ? "inactiveError" : "inactiveValid",
      );
      $stepItem.find(".step-number").removeClass("border-danger");
    }

    // Set text style based on active state
    applyStepTextStyle($stepItem, isActive);

    // Set error indicator class
    $stepItem.toggleClass("has-validation-error", hasError);
  };

  // Improved navigateToStep function with proper fade transitions
  const navigateToStep = (template, targetStep) => {
    // Find the target step item
    const $targetStepItem = $(
      `.step-navigation-item[data-step="${targetStep}"][data-template="${template}"]`,
    );

    if (!$targetStepItem.length) return; // Target step not found

    // Get validation state of all steps before changing active state
    const stepStates = [];
    $(`.step-navigation-item[data-template="${template}"]`).each(function () {
      stepStates.push({
        step: parseInt($(this).data("step")),
        hasError: $(this).hasClass("has-validation-error"),
      });
    });

    // Update all step navigation items while preserving validation state
    $(`.step-navigation-item[data-template="${template}"]`).each(function () {
      const $item = $(this);
      const step = parseInt($item.data("step"));
      const isActive = step === targetStep;

      // Find this step's validation state from our saved states
      const stepState = stepStates.find((s) => s.step === step);
      const hasError = stepState ? stepState.hasError : false;

      // Apply styling
      styleStepNavItem($item, isActive, hasError);
    });

    // Update currentStep variable
    currentStep = targetStep;

    // Properly handle fade transition to ensure it happens every time
    const templateContainer = getTemplateContainer(template);
    const $currentPane = templateContainer.find(
      ".template-steps-content .tab-pane.active",
    );
    const $targetPane = getStepContainer(template, targetStep);

    // First remove 'show' to start fade-out transition
    $currentPane.removeClass("show");

    // After fade-out completes, switch active panes
    setTimeout(() => {
      $currentPane.removeClass("active");
      $targetPane.addClass("active");

      // Then shortly after add 'show' to trigger the fade-in transition
      requestAnimationFrame(() => {
        $targetPane.addClass("show");
      });
    }, 150); // The 150ms delay corresponds to Bootstrap's transition time

    // Update previous/next button states
    const totalSteps = $(
      `.step-navigation-item[data-template="${template}"]`,
    ).length;
    const $previousBtn = templateContainer.find(".previous-step");
    const $nextBtn = templateContainer.find(".next-step");

    $previousBtn.toggleClass("visually-hidden", targetStep === 1);
    $nextBtn.toggleClass("visually-hidden", targetStep === totalSteps);
  };

  // Enhanced validation function with support for validation without UI focus
  const validateCurrentStepInputs = (currentStepContainer, options = {}) => {
    const {
      focusOnError = true,
      markStepInvalid = true,
      skipRequiredNames = [],
    } = options;
    const skippedRequired = new Set(
      skipRequiredNames.map((name) => name.toUpperCase()),
    );
    let isStepValid = true;
    let firstInvalidInput = null;

    // Get step number and template from container
    const stepNumber = currentStepContainer.data("step");
    const template =
      normalizeTemplateId(currentStepContainer.data("templateId")) ||
      currentTemplate;

    // Find the nav item for this step
    const $navItem = $(
      `.step-navigation-item[data-step="${stepNumber}"][data-template="${template}"]`,
    );

    // Count of invalid fields to track
    let invalidFieldsCount = 0;

    currentStepContainer.find(".plugin-setting").each(function () {
      // DEVIATION 4 (one line, not in the monolith) -- skip disabled fields. A disabled field
      // posts nothing AND is excluded from the postable scope by construction: the template
      // disables exactly `not editable and not global` (models/template_steps_body.html:123)
      // and postable_template_scope admits exactly `editable or global` (routes/services.py:545).
      // So validating one can only ever BLOCK a save; it can never prevent a deletion. Without
      // this, a field the user cannot even edit can permanently kill Save -- a stored value that
      // no longer matches a tightened regex, or an external/PRO plugin shipping a Python-only
      // regex (`(?i)`, `(?P<n>)`) that throws in `new RegExp` and is caught below as invalid.
      // The monolith gates the same loop behind a `.save-settings` click this page does not have.
      if (this.disabled) return;

      const $input = $(this);
      let value = $input.val();
      const isRequired =
        $input.prop("required") ||
        String($input.data("required") || "false").toLowerCase() === "true";
      const pattern = $input.attr("pattern");
      // .first(): two <label for> can resolve to the same control (the step
      // body emits one, the widget partial another), and .text() on the whole
      // set concatenates both into the error message.
      let $label = $(`label[for="${$input.attr("id")}"]`).first();
      let fieldName = $input.attr("name") || t("validation.default_field_name");
      const inputName = ($input.attr("name") || "").toUpperCase();
      const skipRequiredCheck = skippedRequired.has(inputName);

      // Handle multiselect hidden inputs
      if (
        $input.is('input[type="hidden"]') &&
        $input.closest(".dropdown").find(".multiselect-toggle").length
      ) {
        const $dropdown = $input.closest(".dropdown");
        const $toggleLabel = $dropdown.find(".multiselect-toggle label");
        if ($toggleLabel.length) {
          $label = $toggleLabel;
        }
      }

      if ($label.length) {
        const i18nKey = $label.attr("data-i18n");
        const labelText = $label
          .text()
          .trim()
          .replace(/\(optional\)$/i, "")
          .replace(/\(\d+ selected\)$/i, "")
          .trim();
        fieldName = i18nKey ? t(i18nKey, labelText) : labelText;
      }

      // Custom error messages
      const requiredMessage = t("validation.required", {
        field: fieldName,
      });
      const patternMessage = t("validation.pattern", {
        field: fieldName,
      });

      let errorMessage = "";
      let isValid = true;
      const hasFileReadError =
        $input.hasClass("plugin-setting-file-text") &&
        Boolean($input.data("fileReadError"));

      if (hasFileReadError) {
        errorMessage = t(
          "template.editor.raw_editor_upload_failed",
          "Unable to read the selected file.",
        );
        isValid = false;
      }

      // Check if the field is required and not empty
      if (isRequired && !skipRequiredCheck && value === "") {
        errorMessage = requiredMessage;
        isValid = false;
      }

      // Validate based on pattern if the input is not empty
      if (isValid && pattern && value !== "") {
        try {
          const regex = buildValidationRegex($input, pattern);
          if (!regex.test(value)) {
            errorMessage = patternMessage;
            isValid = false;
          }
        } catch (e) {
          console.error(
            "Invalid regex pattern:",
            pattern,
            "for input:",
            $input.attr("id"),
          );
          errorMessage = t("validation.pattern", { field: fieldName }); // Generic pattern message on error
          isValid = false;
        }
      }

      const $validationTarget = setFieldValidationState(
        $input,
        isValid,
        errorMessage,
      );

      if (!isValid) {
        isStepValid = false;
        invalidFieldsCount++;

        // Store the first invalid input for focusing later
        if (!firstInvalidInput) {
          firstInvalidInput = $validationTarget;
        }
      }
    });

    // If validation failed and we should focus on errors
    if (!isStepValid && firstInvalidInput && focusOnError) {
      // Scroll the input into view with a small delay to ensure UI has updated
      setTimeout(() => {
        const $setting = firstInvalidInput.closest(".col-12");
        highlightSettings($setting);
        firstInvalidInput.focus();
      }, 100);
    }

    // If requested, mark the step as invalid or valid with improved styling
    if (markStepInvalid) {
      const isActive = $navItem.hasClass("active");
      styleStepNavItem($navItem, isActive, !isStepValid);
    }

    return isStepValid;
  };

  // Pre-save gate. Ported from the easy-mode branch of the monolith's `.save-settings` click
  // handler (plugins-settings.js:2033-2064) — the hijack itself stays out, only the validation
  // moves, and it runs on the native submit instead.
  //
  // Why it has to exist: template_settings_page.html carries `novalidate` (it must — a
  // `pattern` failure on a step pane hidden by `overrides.css:1637`'s
  // `display: none !important` is a control the browser refuses to submit AND refuses to
  // focus, which silently kills Save with no message). That removes the browser's gate, and
  // nothing replaced it. An invalid value then POSTs, and the server does NOT reject the edit
  // — it DELETES the setting: check_variables pops the key (app/models/config.py:193-200)
  // AFTER restore_unowned_settings has already run (routes/services.py:709 then :731), so the
  // key was never a restore candidate, reaches save_config absent, and its stored row is
  // deleted (db_methods/config_save.py:592). The user sees one "Variable X is not valid."
  // flash and their saved value is gone.
  //
  // Scope, honestly: this closes REGEX failures, which is what the browser used to catch. It
  // does NOT close the `normalize_unit` pop at app/models/config.py:222-230 — a size/duration
  // value can satisfy its regex and still be unparseable (`"1s1h"` matches the shipped duration
  // pattern; NGINX's unit-order rule is not expressible in it), and that pops-then-deletes on
  // the same path. Unreachable via the five core templates (their only size/duration settings
  // use the tight `^\d+([kKmMgG])?$`), but a custom template naming e.g.
  // REVERSE_PROXY_READ_TIMEOUT reopens it. The real fix is server-side: check_variables should
  // abort the save instead of popping. This gate is a per-page symptom patch, not that fix.
  //
  // Registered FIRST among this file's handlers, and in the CAPTURE phase on `document`:
  // settings-widgets.js binds its normalisation directly on the form (:1626) from a ready
  // callback that runs before this one (it is loaded first, both `defer`), so a target-phase
  // listener here would run SECOND — normalising a submit we then cancel. That leaves the
  // appended hidden inputs behind, and the next attempt appends them again; `to_dict()` keeps
  // the FIRST value, so a re-edited ace config would save its stale copy. Capture on an
  // ancestor always precedes target-phase listeners on the form regardless of who registered
  // first, and `stopPropagation()` keeps that normalisation from running at all when we block.
  document.addEventListener(
    "submit",
    (event) => {
      const submittedForm = event.target;
      if (
        !submittedForm ||
        typeof submittedForm.matches !== "function" ||
        !submittedForm.matches("form[data-plugin-settings-form]")
      ) {
        return;
      }

      const blockSubmit = () => {
        event.preventDefault();
        event.stopPropagation();
      };

      // Current step first, so the user's own step reports before we move them elsewhere.
      // validateCurrentStepInputs already marks each offending field
      // (setFieldValidationState) and its nav item (styleStepNavItem), so a blocked save is
      // always visible rather than a dead button.
      if (
        !validateCurrentStepInputs(
          getStepContainer(currentTemplate, currentStep),
        )
      ) {
        blockSubmit();
        return;
      }

      // Then every OTHER step — including the ones hidden by `display: none !important`,
      // which is the whole reason this gate exists.
      const totalSteps = $(
        `.step-navigation-item[data-template="${currentTemplate}"]`,
      ).length;
      for (let step = 1; step <= totalSteps; step++) {
        if (step === currentStep) continue;
        if (
          !validateCurrentStepInputs(getStepContainer(currentTemplate, step))
        ) {
          blockSubmit();
          navigateToStep(currentTemplate, step); // surface the FIRST failing step
          return;
        }
      }
    },
    true,
  );

  const resetTemplateConfig = (templateId = currentTemplate, options = {}) => {
    const normalizedTemplate = normalizeTemplateId(templateId);
    if (!normalizedTemplate) return;

    const templateContainer = getTemplateContainer(normalizedTemplate);
    // Hide any override badges shown after fetching global config
    templateContainer
      .find(".global-override-badge")
      .addClass("visually-hidden");
    const isNewService = window.location.pathname.endsWith("/new");
    const useTemplateDefaults =
      isNewService || normalizedTemplate !== usedTemplate;
    // When auto-applying a different template to an EXISTING service (template
    // switch), keep fields the user customized (value differs from the setting
    // default) instead of wiping them to the new template's default. The
    // explicit "Reset template configuration" button passes no flag, so it
    // still performs a full reset. New services have nothing to preserve.
    const preserveCustomizations =
      !!options.preserveCustomizations && useTemplateDefaults && !isNewService;
    const resolveTemplateValue = ($field, fieldId) => {
      const original = $field.data("original");
      const customized =
        preserveCustomizations &&
        original !== undefined &&
        String(original) !== String($field.data("default"));
      if (useTemplateDefaults && !customized) {
        return $(`#${fieldId}-template`).val();
      }
      // jQuery .data() coerces numeric-looking values to numbers; the
      // multiselect/multivalue blocks call .split() on this, so keep a string.
      return original === undefined ? undefined : String(original);
    };

    templateContainer.find("input, select").each(function () {
      const $field = $(this);
      const type = $field.attr("type");
      const templateValue = resolveTemplateValue($field, this.id);

      if ($field.hasClass("plugin-setting-file-upload")) {
        $field.val("");
        return;
      }

      if (
        $field.prop("disabled") ||
        (type === "hidden" && !$field.hasClass("plugin-setting-file-text"))
      ) {
        return;
      }

      // Skip multiselect option checkboxes — handled separately below
      if (
        type === "checkbox" &&
        $field.closest(".multiselect-options").length
      ) {
        return;
      }

      // Check for select element
      if ($field.is("select")) {
        $field.find("option").each(function () {
          $(this).prop("selected", $(this).val() == templateValue);
        });
      } else if (type === "checkbox") {
        $field.prop("checked", templateValue === "yes");
      } else {
        $field.val(templateValue);
        if ($field.hasClass("plugin-setting-file-text")) {
          $field.data("fileReadError", false);
          const originalFileName = String(
            $field.data("originalFileName") || "",
          ).trim();
          setCurrentFileSettingName($field, originalFileName);
          setFieldValidationState($field, true, "");
          syncFileSettingManualInput($field);
          setFileSettingStatus($field);
        }
      }
    });

    // Reset multiselect fields (hidden input + option checkboxes)
    templateContainer
      .find(".multiselect-container input.plugin-setting[type='hidden']")
      .each(function () {
        const $input = $(this);
        if ($input.prop("disabled")) return;
        const templateValue = resolveTemplateValue($input, this.id);
        if (templateValue === undefined) return;

        $input.val(templateValue).trigger("input");
        const $dropdown = $input.closest(".dropdown");
        const separator = $dropdown.data("separator");
        const separatorValue =
          separator === undefined ? " " : String(separator);
        const selectedValues = templateValue
          ? separatorValue === ""
            ? templateValue.split("")
            : templateValue.split(separatorValue)
          : [];
        $dropdown.find(".form-check-input").each(function () {
          const $checkbox = $(this);
          $checkbox.prop("checked", selectedValues.includes($checkbox.val()));
        });
        // Sync badge/footer from the actually-checked boxes (not the parsed
        // token count) and set data-i18n-options so applyTranslations keeps it.
        // The hidden value set above is preserved (no recompute from boxes).
        const checkedCount = $dropdown.find(".form-check-input:checked").length;
        $dropdown
          .find("[data-selected-count]")
          .text(
            t("template.editor.multiselect_summary", {
              count: checkedCount,
              defaultValue: `${checkedCount} selected`,
            }),
          )
          .attr("data-i18n-options", JSON.stringify({ count: checkedCount }));
        $dropdown.find("[data-selected-badge]").text(checkedCount);
      });

    // Reset multivalue fields (hidden input + visible chip rows)
    templateContainer.find(".multivalue-hidden-input").each(function () {
      const $input = $(this);
      if ($input.prop("disabled")) return;
      const templateValue = resolveTemplateValue($input, this.id);
      if (templateValue === undefined) return;

      rebuildMultivalueRows(
        $input.closest(".multivalue-container"),
        templateValue,
      );
    });

    templateContainer.find(".ace-editor").each(function () {
      const editor = ace.edit(this);
      const editorDefault = ($(`#${this.id}-default`).val() || "").trim();
      const $valueEl = $(`#${this.id}-value`);
      // Saved custom-config content (falls back to the template default when the
      // value element is absent, preserving the old reset-to-default behavior).
      const editorSaved = $valueEl.length
        ? ($valueEl.val() || "").trim()
        : editorDefault;
      // Mirror the scalar customized test: keep a custom-config the user edited
      // away from this template's default instead of wiping it on switch.
      const customized =
        preserveCustomizations && editorSaved !== editorDefault;
      const editorValue =
        useTemplateDefaults && !customized ? editorDefault : editorSaved;
      editor.setValue(editorValue);
      editor.session.setValue(editorValue);
      editor.gotoLine(0);
    });

    // Reset to first step with a delay to ensure proper rendering
    setTimeout(() => {
      // Force select the first step
      const firstStep = $(
        `.step-navigation-item[data-step="1"][data-template="${normalizedTemplate}"]`,
      );
      if (firstStep.length) {
        // Set currentStep to ensure proper navigation
        currentStep = 1;

        // Update UI state - properly managing show/active classes
        $(`.step-navigation-item[data-template="${normalizedTemplate}"]`).each(
          function () {
            const $item = $(this);
            const step = parseInt($item.data("step"));
            const isActive = step === 1; // First step is active

            // Apply styling with proper classes
            styleStepNavItem($item, isActive, false);
          },
        );

        // Show the first step content with proper fade transition
        const stepId = firstStep.data("step-id");
        // Find all active panes and remove show first
        const $activePanes = templateContainer.find(
          ".template-steps-content .tab-pane.active",
        );
        $activePanes.removeClass("show");

        // After fade-out completes, switch active panes
        setTimeout(() => {
          $activePanes.removeClass("active");
          const $targetPane = $(`#${stepId}`);
          $targetPane.addClass("active");

          // Then trigger fade-in
          requestAnimationFrame(() => {
            $targetPane.addClass("show");
          });
        }, 150);

        // Update button states
        const $previousButton = templateContainer.find(".previous-step");
        if (!$previousButton.hasClass("visually-hidden")) {
          $previousButton.addClass("visually-hidden");
        }

        const $stepItems = $(
          `.step-navigation-item[data-template="${normalizedTemplate}"]`,
        );
        const $nextButton = templateContainer.find(".next-step");
        if ($stepItems.length > 1) {
          $nextButton.removeClass("visually-hidden");
        } else if (!$nextButton.hasClass("visually-hidden")) {
          $nextButton.addClass("visually-hidden");
        }
      }
    }, 100);
  };

  // Unified and improved step navigation handler
  $(document).on(
    "click",
    ".step-navigation-item, .next-step, .previous-step",
    function (e) {
      // Determine if we're handling a direct step click or a next/prev button
      const isDirectStepClick = $(this).hasClass("step-navigation-item");
      const isNextButton = $(this).hasClass("next-step");
      const isPrevButton = $(this).hasClass("previous-step");

      // Skip action if button is visually-hidden
      if (
        (isNextButton || isPrevButton) &&
        $(this).hasClass("visually-hidden")
      ) {
        return;
      }

      // Get template and determine target step
      let template, targetStep;

      if (isDirectStepClick) {
        targetStep = parseInt($(this).data("step"));
        template = normalizeTemplateId($(this).data("template"));

        // Don't proceed if already on this step
        if (targetStep === currentStep) return;
      } else {
        template = normalizeTemplateId($(this).data("template"));
        targetStep = isNextButton ? currentStep + 1 : currentStep - 1;
      }

      if (!template) template = currentTemplate;

      // Always validate current step to update its validation state
      // regardless of whether we're going forward or backward
      const currentStepContainer = getStepContainer(template, currentStep);

      // Validate but don't block navigation - just update the UI indicators
      validateCurrentStepInputs(currentStepContainer, {
        focusOnError: false,
        markStepInvalid: true,
      });

      // Only block forward navigation if validation fails
      if (targetStep > currentStep) {
        const isStepValid = validateCurrentStepInputs(currentStepContainer, {
          focusOnError: true,
          markStepInvalid: true,
        });

        if (!isStepValid) {
          return; // Don't navigate forward if validation fails
        }
      }

      // If we get here, navigate to the target step
      navigateToStep(template, targetStep);
    },
  );

  // Add improved input event handler to update validation status immediately
  $(document).on("input change", ".plugin-setting", function () {
    // Find the step container for this input
    const stepContainer = $(this).closest(".tab-pane");
    if (!stepContainer.length) return;

    // Debounce to avoid excessive validation
    debounce(() => {
      // Get the template and step number
      const template =
        normalizeTemplateId(stepContainer.data("templateId")) ||
        currentTemplate;
      const step = parseInt(stepContainer.data("step"));

      // Validate without focusing
      const isStepValid = validateCurrentStepInputs(stepContainer, {
        focusOnError: false,
        markStepInvalid: true,
      });

      // Update the step indicator styling
      const $stepItem = $(
        `.step-navigation-item[data-step="${step}"][data-template="${template}"]`,
      );

      if ($stepItem.length) {
        const isActive = step === currentStep;
        styleStepNavItem($stepItem, isActive, !isStepValid);
      }
    }, 200)();
  });

  $("#reset-template-config").on("click", function () {
    const reset_modal = $("#modal-reset-template-config");
    reset_modal.modal("show");
  });

  $("#confirm-reset-template-config").on("click", function () {
    resetTemplateConfig();
  });

  $("#fetch-global-config").on("click", function () {
    if (isReadOnly) {
      alert(t("alert.readonly_mode"));
      return;
    }
    const fetchModal = $("#modal-fetch-global-config");
    // Ensure modal is attached to body to avoid z-index/overflow issues
    fetchModal.appendTo("body").modal("show");
  });

  $("#confirm-fetch-global-config").on("click", function () {
    $.ajax({
      // Relative on purpose: dropping the last FOUR segments of the current path
      // (services/<svc>/templates/<tpl>) leaves whatever prefix the UI is mounted under, so
      // this keeps working behind REVERSE_PROXY_URL. The monolith drops two because it runs
      // on /services/<svc> and /global-settings. NEVER hardcode "/global-settings": a
      // misdirected request carries the __Host- session cookie.
      url: `${window.location.pathname
        .split("/")
        .slice(0, -4)
        .join("/")}/global-settings?as_json=true`,
      type: "GET",
      success: function (globalConfig) {
        const templateContainer = getTemplateContainer(currentTemplate);

        const settingsInTemplate = new Set();
        templateContainer.find(".plugin-setting").each(function () {
          settingsInTemplate.add($(this).attr("name"));
        });

        for (const settingName in globalConfig) {
          if (settingsInTemplate.has(settingName)) {
            if (settingName === "SERVER_NAME") {
              continue;
            }
            const settingData = globalConfig[settingName];
            const settingValue = settingData.value;
            const $input = templateContainer.find(`[name="${settingName}"]`);

            if (!$input.length) continue;

            const defaultValue = $input.data("default");
            if (settingValue === defaultValue) {
              continue;
            }

            const $settingContainer = $input.closest(".col-12");
            const $badge = $settingContainer.find(".global-override-badge");
            if ($badge.length) {
              $badge.removeClass("visually-hidden");
            }

            const inputType = $input.attr("type");

            if ($input.is("select")) {
              $input.val(settingValue).trigger("change");
            } else if (inputType === "checkbox") {
              $input.prop("checked", settingValue === "yes").trigger("change");
            } else if ($input.hasClass("plugin-setting-file-text")) {
              $input.data("fileReadError", false);
              $input.val(settingValue).trigger("input").trigger("change");
              setCurrentFileSettingName(
                $input,
                String(settingData.file_name || "").trim(),
              );
              setFieldValidationState($input, true, "");
              syncFileSettingManualInput($input);
              setFileSettingStatus($input);
            } else if ($input.hasClass("multivalue-hidden-input")) {
              rebuildMultivalueRows(
                $input.closest(".multivalue-container"),
                settingValue,
              );
            } else if (
              $input.is('input[type="hidden"]') &&
              $input.closest(".dropdown").find(".multiselect-toggle").length
            ) {
              $input.val(settingValue).trigger("input");
              const $dropdown = $input.closest(".dropdown");
              const separator = $dropdown.data("separator");
              const separatorValue =
                separator === undefined ? " " : String(separator);
              const selectedValues = settingValue
                ? separatorValue === ""
                  ? settingValue.split("")
                  : settingValue.split(separatorValue)
                : [];
              $dropdown.find(".form-check-input").each(function () {
                const $checkbox = $(this);
                const checkboxVal = $checkbox.val();
                $checkbox.prop("checked", selectedValues.includes(checkboxVal));
              });
              updateMultiselectDisplay($dropdown);
            } else {
              // Handle simple text-like inputs and textareas
              $input.val(settingValue).trigger("input");
            }
          }
        }

        const feedbackToast = $("#feedback-toast").clone();
        feedbackToast.attr("id", `feedback-toast-${toastNum++}`);
        feedbackToast.find("span").text(t("status.success", "Success"));
        feedbackToast
          .find(".fw-medium")
          .text(
            t("toast.global_settings_applied_title", "Global settings applied"),
          )
          .attr("data-i18n", "toast.global_settings_applied_title");
        feedbackToast
          .find("div.toast-body")
          .text(
            t(
              "toast.global_settings_applied_body",
              "Global settings have been successfully fetched and applied to the current form.",
            ),
          )
          .attr("data-i18n", "toast.global_settings_applied_body");
        feedbackToast.removeClass("border-warning").addClass("border-success");
        feedbackToast
          .find(".toast-header")
          .removeClass("text-warning")
          .addClass("text-success");
        feedbackToast.appendTo("#feedback-toast-container");
        feedbackToast.toast("show");
      },
      error: function () {
        const feedbackToast = $("#feedback-toast").clone();
        feedbackToast.attr("id", `feedback-toast-${toastNum++}`);
        feedbackToast.find("span").text(t("flash.error", "Error"));
        feedbackToast
          .find(".fw-medium")
          .text(
            t(
              "toast.global_settings_failed_title",
              "Failed to fetch global settings",
            ),
          )
          .attr("data-i18n", "toast.global_settings_failed_title");
        feedbackToast
          .find("div.toast-body")
          .text(
            t(
              "toast.global_settings_failed_body",
              "An error occurred while fetching global settings.",
            ),
          )
          .attr("data-i18n", "toast.global_settings_failed_body");
        feedbackToast.removeClass("border-warning").addClass("border-danger");
        feedbackToast
          .find(".toast-header")
          .removeClass("text-warning")
          .addClass("text-danger");
        feedbackToast.appendTo("#feedback-toast-container");
        feedbackToast.toast("show");
      },
    });
  });

  // Registered LAST on purpose. `ace.edit()` below is the one call in this file that can
  // throw at ready time (ace missing, 404'd, CSP-blocked) -- and a throw inside a jQuery
  // .each callback aborts the rest of this closure. With the block here, that costs the
  // editors and the theme sync; with it at the top it would ALSO silently kill every step
  // navigation, every validation, Reset and Fetch Global, since all of those register below.
  // Same ordering rule as settings-widgets.js's submit listener, same reason.
  var editors = [];
  var editorRegistry = {};

  $(".ace-editor").each(function () {
    const $editorElement = $(this);
    const sourceSelector = $editorElement.data("source");
    const $source = sourceSelector ? $(sourceSelector) : null;
    let initialContent = "";

    if ($source && $source.length) {
      if ($source.is("textarea, input")) {
        initialContent = $source.val() || "";
      } else {
        initialContent = ($source.text() || "").trim();
      }
    } else {
      initialContent = $editorElement.text().trim();
    }

    const editor = ace.edit(this);

    editor.session.setMode("ace/mode/nginx");
    // const language = $(this).data("language"); // TODO: Support ModSecurity
    // if (language === "NGINX") {
    //   editor.session.setMode("ace/mode/nginx");
    // } else {
    //   editor.session.setMode("ace/mode/text"); // Default mode if language is unrecognized
    // }

    const method = $editorElement.data("method");
    const explicitReadOnly = $editorElement.data("readonly");
    if (typeof explicitReadOnly !== "undefined") {
      editor.setReadOnly(
        explicitReadOnly === true || explicitReadOnly === "true",
      );
    } else if (method !== "ui" && method !== "api" && method !== "default") {
      editor.setReadOnly(true);
    }

    // Set the editor's initial content
    editor.setValue(initialContent, -1); // The second parameter moves the cursor to the start

    editor.setOptions({
      fontSize: "14px",
      showPrintMargin: false,
      tabSize: 2,
      useSoftTabs: true,
      wrap: true,
    });

    editor.renderer.setPadding(12);
    editor.renderer.setScrollMargin(16, 16);
    editors.push(editor);

    const elementId = $editorElement.attr("id");
    if (elementId) {
      editorRegistry[elementId] = editor;
    }

    // LOAD-BEARING -- do not drop. The mirror textarea (#<id>-value) is the ONLY thing
    // settings-widgets.js's submit handler reads to build the POST field for this editor
    // (it never touches the `ace` global). Without this sync the mirror keeps its
    // server-rendered value, so value === defaultValue for every editor, no hidden input is
    // appended, and every custom-config edit vanishes on save with no error and no flash.
    if ($source && $source.length && $source.is("textarea, input")) {
      $source.val(editor.getValue());
      editor.on("change", () => {
        $source.val(editor.getValue());
      });
    }
  });

  var theme = $("#theme").val();

  function setEditorTheme() {
    editors.forEach((editor) => {
      if (theme === "dark") {
        editor.setTheme("ace/theme/cloud9_night");
      } else {
        editor.setTheme("ace/theme/cloud9_day");
      }
    });
  }

  setEditorTheme();

  $("#dark-mode-toggle").on("change", function () {
    setTimeout(() => {
      theme = $("#theme").val();
      setEditorTheme();
    }, 30);
  });
});
