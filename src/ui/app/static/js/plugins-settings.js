$(document).ready(() => {
  // Ensure i18next is loaded before using it
  const t = typeof i18next !== "undefined" ? i18next.t : (key) => key; // Fallback

  let toastNum = 0;
  let currentPlugin = "general";
  let currentStep = 1;
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  let isInit = true;

  if (isReadOnly && window.location.pathname.endsWith("/new"))
    window.location.href = window.location.href.split("/new")[0];

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

  const $templateInput = $("#used-template");
  let usedTemplate = "low";
  if ($templateInput.length) {
    const normalizedUsedTemplate = normalizeTemplateId($templateInput.val());
    usedTemplate = normalizedUsedTemplate !== "" ? normalizedUsedTemplate : "";
  }

  let currentTemplate = normalizeTemplateId($("#selected-template").val());
  let currentMode = normalizeTemplateId($("#selected-mode").val());
  let currentType = normalizeTemplateId($("#selected-type").val());

  if (!currentTemplate) currentTemplate = usedTemplate;
  if (!currentMode) currentMode = "easy";
  if (!currentType) currentType = "all";

  const $serviceMethodInput = $("#service-method");
  const $pluginTypeSelect = $("#plugin-type-select");
  const $pluginKeywordSearch = $("#plugin-keyword-search");
  const $pluginKeywordSearchTop = $("#plugin-keyword-search-top");
  const $pluginItems = $(".plugin-navigation-item");
  const $templateSearch = $("#template-search");
  const $templateDropdownMenu = $("#templates-dropdown-menu");
  const $templateDropdownItems = $("#templates-dropdown-menu li.nav-item");

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

  $("#templates-dropdown-menu button[data-template-id]").each(function () {
    const $button = $(this);
    const templateId = normalizeTemplateId($button.data("template-id"));
    const domId = normalizeTemplateId($button.data("template-dom-id"));
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

  const getTemplateTabButton = (templateId) => {
    const key = normalizeTemplateId(templateId);
    if (!key) return $();
    return $(`#templates-dropdown-menu button[data-template-id="${key}"]`);
  };

  const updateUrlParams = (params, removeHash = false) => {
    const newUrl = new URL(window.location.href);
    const searchParams = new URLSearchParams(newUrl.search);

    Object.entries(params).forEach(([key, value]) => {
      if (value === null || value === undefined) {
        searchParams.delete(key);
      } else {
        searchParams.set(key, value);
      }
    });

    const serializedSearch = searchParams.toString().replace(/\+/g, "%20");
    newUrl.search = serializedSearch ? `?${serializedSearch}` : "";
    if (removeHash) {
      newUrl.hash = "";
    }

    history.pushState(params, document.title, newUrl.toString());
  };

  const updateTemplateUrl = (templateId, { clearType = false } = {}) => {
    const params = {};
    if (clearType) params.type = null;

    const normalizedTemplate = normalizeTemplateId(templateId);
    if (
      currentMode === "easy" &&
      normalizedTemplate &&
      normalizedTemplate !== "low"
    ) {
      params.template = normalizedTemplate;
    } else {
      params.template = null;
    }

    updateUrlParams(params);
  };

  const showTemplateTab = (templateId) => {
    const $button = getTemplateTabButton(templateId);
    if ($button.length) {
      $button.tab("show");
    }
  };

  const setCurrentTemplate = (templateId, { clearType = false } = {}) => {
    const normalized = normalizeTemplateId(templateId);
    if (!normalized) return;
    currentTemplate = normalized;
    // Ensure we have a DOM id mapping for this template
    getTemplateDomId(currentTemplate);

    const $selectedTemplateField = $("#selected-template");
    if ($selectedTemplateField.length)
      $selectedTemplateField.val(currentTemplate);

    updateTemplateUrl(currentTemplate, { clearType });
  };

  setCurrentTemplate(currentTemplate);

  const handleModeChange = (targetClass) => {
    currentMode = targetClass.substring(1).replace("navs-modes-", "");

    // Prepare params for the URL update
    const params = {};
    params.mode = currentMode;
    if (currentMode === "advanced" && currentType !== "all")
      params.type = currentType;
    if (currentMode === "easy" && currentTemplate !== "low")
      params.template = currentTemplate;

    // If "easy" is selected, remove the "mode" parameter
    if (currentMode === "easy") {
      params.mode = null; // Set mode to null to remove it from the URL
      params.type = null; // Remove the type parameter
      updateUrlParams(params, true); // Call the function without the hash (keep it intact)
    } else {
      if (currentMode === "advanced" && !$("#navs-modes-easy").length) {
        params.mode = null; // Remove the mode parameter
      }

      // If another mode is selected, update the "mode" parameter
      params.template = null; // Remove the template parameter
      if (currentMode === "advanced" && currentPlugin !== "general") {
        // Update the URL hash to the current plugin (e.g., #plugin-name)
        window.location.hash = currentPlugin;
      } else if (currentMode === "raw") {
        params.type = null; // Remove the type parameter
      }
      updateUrlParams(params, currentMode === "raw"); // Keep the mode in the URL
    }
  };

  const resetTemplateConfig = (templateId = currentTemplate) => {
    const normalizedTemplate = normalizeTemplateId(templateId);
    if (!normalizedTemplate) return;

    const templateContainer = getTemplateContainer(normalizedTemplate);
    // Hide any override badges shown after fetching global config
    templateContainer
      .find(".global-override-badge")
      .addClass("visually-hidden");
    templateContainer.find("input, select").each(function () {
      const type = $(this).attr("type");
      const isNewEndpoint = window.location.pathname.endsWith("/new");
      const templateValue = isNewEndpoint
        ? $(`#${this.id}-template`).val()
        : $(this).data("original");
      if ($(this).prop("disabled") || type === "hidden") {
        return;
      }

      // Check for select element
      if ($(this).is("select")) {
        $(this)
          .find("option")
          .each(function () {
            $(this).prop("selected", $(this).val() == templateValue);
          });
      } else if (type === "checkbox") {
        $(this).prop("checked", templateValue === "yes");
      } else {
        $(this).val(templateValue);
      }
    });

    templateContainer.find(".ace-editor").each(function () {
      const editor = ace.edit(this);
      const editorValue = $(`#${this.id}-default`).val().trim();
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

  // Enhanced handleTabChange function with validation check
  const handleTabChange = (targetClass, options = {}) => {
    const { templateId: explicitTemplateId } = options;
    // If we're changing templates in easy mode, validate current step first
    if (
      targetClass.includes("navs-templates-") &&
      currentMode === "easy" &&
      !isInit
    ) {
      const currentStepContainer = getStepContainer(
        currentTemplate,
        currentStep,
      );

      // Only proceed if validation passes
      if (
        !validateCurrentStepInputs(currentStepContainer, {
          skipRequiredNames: ["SERVER_NAME"],
        })
      ) {
        // If validation fails, prevent the tab change
        return false;
      }
    }

    // Prepare the params for URL (parameters to be updated in the URL)
    const params = {};
    if (currentMode !== ($("#navs-modes-easy").length ? "easy" : "advanced"))
      params.mode = currentMode;
    if (currentType !== "all") params.type = currentType;

    if (targetClass.includes("navs-plugins-")) {
      currentPlugin = targetClass.substring(1).replace("navs-plugins-", "");

      // If "general" is selected and a hash exists, remove the hash but keep the parameters
      if (currentPlugin === "general" && window.location.hash) {
        // Call updateUrlParams with `removeHash = true` to remove the hash fragment
        updateUrlParams(params, true);
      } else {
        // Update the URL hash to the current plugin (e.g., #plugin-name)
        window.location.hash = currentPlugin;

        // Also update the URL parameters (if any exist) while preserving the hash
        updateUrlParams(params);
      }
    } else if (targetClass.includes("navs-templates-")) {
      const previousTemplate = currentTemplate;
      const targetDomId = targetClass
        .substring(1)
        .replace("navs-templates-", "");

      let nextTemplateId =
        explicitTemplateId || domIdToTemplateIdMap[targetDomId] || "";

      if (!nextTemplateId) {
        const $targetPane = $(targetClass);
        if ($targetPane.length) {
          nextTemplateId = $targetPane.data("template-id") || "";
        }
      }

      if (nextTemplateId)
        setCurrentTemplate(nextTemplateId, { clearType: true });

      if (!isInit) resetTemplateConfig(previousTemplate);
    }

    return true; // Tab change is allowed
  };

  const highlightSettings = (matchedSettings, fadeTimeout = 600) => {
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
      const $input = $(this);
      let value = $input.val();
      const isRequired = $input.prop("required");
      const pattern = $input.attr("pattern");
      let $label = $(`label[for="${$input.attr("id")}"]`);
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

      // Check if the field is required and not empty
      if (isRequired && !skipRequiredCheck && value === "") {
        errorMessage = requiredMessage;
        isValid = false;
      }

      // Validate based on pattern if the input is not empty
      if (isValid && pattern && value !== "") {
        try {
          const regex = new RegExp(pattern);
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

      // Toggle valid/invalid classes
      $input.toggleClass("is-invalid", !isValid);

      // Manage the invalid-feedback element
      let $feedback = $input.next(".invalid-feedback");
      if (!$feedback.length) {
        $feedback = $('<div class="invalid-feedback"></div>').insertAfter(
          $input,
        );
      }

      if (!isValid) {
        $feedback.text(errorMessage);
        isStepValid = false;
        invalidFieldsCount++;

        // Store the first invalid input for focusing later
        if (!firstInvalidInput) {
          firstInvalidInput = $input;
        }
      } else {
        $feedback.text("");
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

  const getFormFromSettings = (elem) => {
    const form = $("<form>", {
      method: "POST",
      action: window.location.href,
      class: "visually-hidden",
    });

    // Helper function to append hidden inputs
    const appendHiddenInput = (form, name, value) => {
      form.append(
        $("<input>", {
          type: "hidden",
          name: name,
          value: value,
        }),
      );
    };

    const addChildrenToForm = (form, elem, isEasy = false) => {
      elem.find("input, select").each(function () {
        const $this = $(this);
        const settingType = $this.attr("type");

        if (settingType === "hidden") return;

        const settingName = $this.attr("name");
        let settingValue = $this.val();

        if ($this.is("select")) {
          settingValue = $this.val();
        } else if (settingType === "checkbox") {
          settingValue = $this.is(":checked") ? "yes" : "no";
        }

        appendHiddenInput(form, settingName, settingValue);
      });

      // Handle multiselect dropdowns
      elem
        .find(".dropdown")
        .has(".multiselect-toggle")
        .each(function () {
          const $dropdown = $(this);
          const $hiddenInput = $dropdown.find(
            'input[type="hidden"].plugin-setting',
          );

          if ($hiddenInput.length && $hiddenInput.attr("name")) {
            const settingName = $hiddenInput.attr("name");
            const settingValue = $hiddenInput.val() || "";
            appendHiddenInput(form, settingName, settingValue);
          }
        });

      // Handle multivalue containers
      elem.find(".multivalue-container").each(function () {
        const $container = $(this);
        const $hiddenInput = $container.find(".multivalue-hidden-input");

        if ($hiddenInput.length && $hiddenInput.attr("name")) {
          const settingName = $hiddenInput.attr("name");
          const settingValue = $hiddenInput.val() || "";
          appendHiddenInput(form, settingName, settingValue);
        }
      });
    };

    // Handle missing CSRF token gracefully
    const csrfToken = $("#csrf_token").val() || "";
    appendHiddenInput(form, "csrf_token", csrfToken);

    if (currentMode === "easy") {
      appendHiddenInput(form, "USE_TEMPLATE", currentTemplate);

      const templateContainer = getTemplateContainer(currentTemplate);
      addChildrenToForm(form, templateContainer, true);

      templateContainer.find(".ace-editor").each(function () {
        const editor = ace.edit(this);
        const editorValue = editor.getValue().trim();
        const editorDefault = $(`#${this.id}-default`).val().trim();
        if (editorValue !== editorDefault)
          appendHiddenInput(form, $(this).data("name"), editorValue);
      });

      // Append 'IS_DRAFT' if it exists
      const $draftInput = $("#is-draft");
      if ($draftInput.length) {
        appendHiddenInput(form, "IS_DRAFT", $draftInput.val());
      }
    } else if (currentMode === undefined || currentMode === "advanced") {
      addChildrenToForm(form, $("div[id^='navs-plugins-']"));

      const $draftInput = $("#is-draft");
      if ($draftInput.length) {
        appendHiddenInput(form, "IS_DRAFT", $draftInput.val());
      }
    } else if (currentMode === "raw") {
      // Helper function to parse configuration strings into an object
      const parseConfig = (selector) => {
        const rawConfig = $(selector).val();
        if (!rawConfig) return {};
        return rawConfig
          .trim()
          .split("\n")
          .reduce((acc, line) => {
            const [key, ...valueParts] = line
              .split("=")
              .map((str) => str.trim());
            const value = valueParts.join("=");
            if (key && value !== undefined) {
              acc[key.trim()] = value.trim();
            }
            return acc;
          }, {});
      };

      // Parse original and default configurations
      const entireconfigOriginals = parseConfig("#raw-entire-config");
      const configDefaults = parseConfig("#raw-config-defaults");

      // Sets to keep track of processed keys
      const formKeys = new Set();
      const skippedKeys = new Set();

      // Process the current configuration
      const $rawConfig = $("#raw-config");
      if ($rawConfig.length) {
        const configLines = $rawConfig
          .val()
          .split("\n")
          .map((line) => line.trim())
          .filter((line) => line && !line.startsWith("#"));

        configLines.forEach((line) => {
          const [key, ...valueParts] = line.split("=").map((str) => str.trim());
          const value = valueParts.join("=");
          if (!key || value === undefined) {
            console.warn(`Skipping malformed line: ${line}`);
            return;
          }

          appendHiddenInput(form, key, value);
          formKeys.add(key);
        });
      }

      // Append default values if they are not already in the form and not skipped
      Object.entries(configDefaults).forEach(([key, value]) => {
        if (!formKeys.has(key) && !skippedKeys.has(key)) {
          appendHiddenInput(form, key, value);
          formKeys.add(key);
        }
      });

      // Append original values if they are not already in the form and not skipped
      Object.entries(entireconfigOriginals).forEach(([key, value]) => {
        if (!formKeys.has(key) && !skippedKeys.has(key)) {
          appendHiddenInput(form, key, value);
          formKeys.add(key);
        }
      });
    }

    // Append 'OLD_SERVER_NAME' if it exists
    const $oldServerName = $("#old-server-name");
    if ($oldServerName.length) {
      appendHiddenInput(form, "OLD_SERVER_NAME", $oldServerName.val());
    }

    return form;
  };

  $("#select-template").on("click", () => $templateSearch.focus());

  $("#template-search").on(
    "input",
    debounce((e) => {
      const inputValue = e.target.value.toLowerCase();
      let visibleItems = 0;

      $templateDropdownItems.each(function () {
        const item = $(this);
        const matches = item.text().toLowerCase().includes(inputValue);

        item.toggle(matches);

        if (matches) {
          visibleItems++; // Increment when an item is shown
        }
      });

      if (visibleItems === 0) {
        if ($templateDropdownMenu.find(".no-template-items").length === 0) {
          $templateDropdownMenu.append(
            `<li class="no-template-items dropdown-item text-muted">${t(
              "status.no_item",
            )}</li>`,
          );
        }
      } else {
        $templateDropdownMenu.find(".no-template-items").remove();
      }
    }, 50),
  );

  $(document).on("hidden.bs.dropdown", "#select-template", function () {
    $("#template-search").val("").trigger("input");
  });

  // Attach event listener to handle mode changes when tabs are switched
  $('.mode-selection-menu button[data-bs-toggle="tab"]').on(
    "shown.bs.tab",
    (e) => {
      handleModeChange($(e.target).data("bs-target"));
    },
  );

  // Add validation to tab clicks for plugin/template changes
  $('#plugins-dropdown-menu button[data-bs-toggle="tab"]').on(
    "click",
    function (e) {
      // Always allow tab changes in advanced mode
      if (currentMode !== "easy") return;

      // In easy mode, ensure there are no validation errors in the current template
      const currentStepContainer = getStepContainer(
        currentTemplate,
        currentStep,
      );

      if (
        !validateCurrentStepInputs(currentStepContainer, {
          skipRequiredNames: ["SERVER_NAME"],
        })
      ) {
        e.preventDefault(); // Prevent tab change
        e.stopPropagation(); // Stop event bubbling
        return false;
      }
    },
  );

  $('#plugins-dropdown-menu button[data-bs-toggle="tab"]').on(
    "shown.bs.tab",
    (e) => {
      handleTabChange($(e.target).data("bs-target"));
    },
  );

  $('#templates-dropdown-menu button[data-bs-toggle="tab"]').on(
    "click",
    function (e) {
      // Skip validation for initial load or if not in easy mode
      if (isInit || currentMode !== "easy") return;

      // Validate current step before allowing template change
      const currentStepContainer = getStepContainer(
        currentTemplate,
        currentStep,
      );

      if (
        !validateCurrentStepInputs(currentStepContainer, {
          skipRequiredNames: ["SERVER_NAME"],
        })
      ) {
        e.preventDefault(); // Prevent tab change
        e.stopPropagation(); // Stop event bubbling
        return false;
      }
    },
  );

  $('#templates-dropdown-menu button[data-bs-toggle="tab"]').on(
    "shown.bs.tab",
    (e) => {
      const $target = $(e.target);
      const templateId = normalizeTemplateId($target.data("template-id"));
      if (!handleTabChange($(e.target).data("bs-target"), { templateId })) {
        // If handleTabChange returns false, revert to the previous tab
        showTemplateTab(currentTemplate);
        return;
      }
    },
  );

  $(".plugin-navigation-item").on("click", function (e) {
    e.preventDefault();
    const tab = bootstrap.Tab.getOrCreateInstance(this);
    tab.show();
  });

  $(".plugin-navigation-item").on("shown.bs.tab", function (e) {
    const targetClass = $(e.target).data("bs-target");
    handleTabChange(targetClass);
  });

  // Update the mode change handler to validate before switching from easy mode
  $('.mode-selection-menu button[data-bs-toggle="tab"]').on(
    "click",
    function (e) {
      const targetMode = $(this)
        .data("bs-target")
        .substring(1)
        .replace("navs-modes-", "");

      // If switching from easy mode, validate current step first
      if (currentMode === "easy" && targetMode !== "easy") {
        const currentStepContainer = getStepContainer(
          currentTemplate,
          currentStep,
        );

        if (!validateCurrentStepInputs(currentStepContainer)) {
          e.preventDefault(); // Prevent tab change
          e.stopPropagation(); // Stop event bubbling
          return false;
        }
      }
    },
  );

  $(document).on("input", ".plugin-setting", function () {
    debounce(() => {
      const isValid = $(this).attr("pattern")
        ? new RegExp($(this).attr("pattern")).test($(this).val())
        : true;
      $(this)
        .toggleClass("is-valid", isValid)
        .toggleClass("is-invalid", !isValid);
    }, 100)();
  });

  $(document).on("focusout", ".plugin-setting", function () {
    $(this).removeClass("is-valid");
  });

  const filterPluginList = () => {
    const keyword = $pluginKeywordSearch.val().toLowerCase().trim();
    let firstVisible = null;
    let visibleItems = 0;

    $pluginItems.each(function () {
      const $item = $(this);
      const typeMatches =
        currentType === "all" || $item.data("type") === currentType;

      const pluginId = $item.data("plugin");
      const pluginName = $item.find(".fw-bold").text().toLowerCase();
      const pluginDesc = $item
        .find("small.text-muted.d-block")
        .data("description")
        .toLowerCase();
      const keywordMatches =
        keyword === "" ||
        pluginId.includes(keyword) ||
        pluginName.includes(keyword) ||
        pluginDesc.includes(keyword);

      if (typeMatches && keywordMatches) {
        $item.removeClass("visually-hidden");
        if (!firstVisible) {
          firstVisible = $item;
        }
        visibleItems++;
      } else {
        $item.addClass("visually-hidden");
      }
    });

    $(".no-plugin-items").toggle(visibleItems === 0);

    const $activeNav = $(".plugin-navigation-item.active");
    if (
      firstVisible &&
      ($activeNav.length === 0 || $activeNav.hasClass("visually-hidden"))
    ) {
      const tab = bootstrap.Tab.getOrCreateInstance(firstVisible[0]);
      tab.show();
    }
  };

  // Helpers near your other utils
  const safeLower = (v) => (v == null ? "" : String(v)).toLowerCase();
  const scoreMatch = (text, kw) => {
    text = safeLower(text);
    if (!kw || !text) return 0;
    if (text === kw) return 100;
    if (text.startsWith(kw)) return 60;
    if (text.includes(kw)) return 30;
    return 0;
  };

  const performSettingsSearch = () => {
    const keyword = safeLower($pluginKeywordSearchTop.val()).trim();

    // Clear any previous highlight
    $(".tab-content .tab-pane .setting-highlight").removeClass(
      "setting-highlight setting-highlight-fade",
    );

    if (!keyword) return;

    const activePlugin = currentPlugin; // kept up to date in handleTabChange
    let best = null;

    $("div[id^='navs-plugins-']").each(function () {
      const $pluginContainer = $(this);
      const pluginId = $pluginContainer.attr("id").replace("navs-plugins-", "");

      // --- Plugin meta (left nav item) ---
      const $navItem = $(`#plugin-nav-${pluginId}`);
      const pluginName = safeLower($navItem.find(".fw-bold").text());
      const pluginDesc = safeLower(
        $navItem.find("small.text-muted.d-block").data("description"),
      );
      const metaScore =
        scoreMatch(pluginId, keyword) +
        scoreMatch(pluginName, keyword) +
        scoreMatch(pluginDesc, keyword);

      // --- Settings in this plugin ---
      // We look at: friendly header label, the floating setting key label, and the *help* badge tooltip.
      const settings = [];
      $pluginContainer
        .find("[class*='col-12']") // each setting block container
        .each(function () {
          const $block = $(this);

          // Friendly label (header)
          const headerLabel = safeLower(
            $block.find("label.form-label").first().text(),
          );

          // Setting key (floating label inside control)
          const settingKey = safeLower(
            $block.find("label.text-truncate").first().text(),
          );

          // Help tooltip (only the help badge with question mark icon)
          const helpBadge = $block.find(".bx-question-mark").closest(".badge");
          const helpText = safeLower(helpBadge.attr("data-bs-original-title"));

          // Compute the best score for this block
          const s = Math.max(
            scoreMatch(headerLabel, keyword),
            scoreMatch(settingKey, keyword),
            Math.floor(scoreMatch(helpText, keyword) / 2), // help less weighted
          );

          if (s > 0) {
            settings.push({ node: $block[0], score: s });
          }
        });

      // Total score with strong bias for the active plugin
      const bias = pluginId === activePlugin ? 1000 : 0;
      const settingsTotal = settings.reduce((sum, x) => sum + x.score, 0);
      const total = bias + metaScore + settingsTotal;

      // Sort settings by their own score (best first)
      settings.sort((a, b) => b.score - a.score);

      if (!best || total > best.total) {
        best = { pluginId, total, settings };
      }
    });

    if (!best) return;

    const $bestNav = $(`#plugin-nav-${best.pluginId}`);
    const doHighlight = () => {
      if (best.settings.length) {
        // Convert to DOM nodes array for jQuery
        highlightSettings($(best.settings.map((s) => s.node)));
      }
    };

    if ($bestNav.hasClass("active")) {
      doHighlight();
    } else {
      $bestNav.one("shown.bs.tab", doHighlight);
      bootstrap.Tab.getOrCreateInstance($bestNav[0]).show();
    }
  };

  const debouncedFilterPluginList = debounce(filterPluginList, 200);
  const debouncedSettingsSearch = debounce(performSettingsSearch, 200);

  $pluginKeywordSearch.on("input", debouncedFilterPluginList);

  $pluginKeywordSearchTop.on("input", debouncedSettingsSearch);

  $pluginTypeSelect.on("change", function () {
    currentType = $(this).val();
    const params =
      currentType === "all" ? { type: null } : { type: currentType };

    updateUrlParams(params);
    filterPluginList(); // Not debounced for instant feedback
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

  $(".add-multiple").on("click", function () {
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
      const defaultVal = element.data("default") || "";

      // Safeguard checks for missing attributes
      const originalId = element.attr("id") || "";
      const originalLabelledBy = element.attr("aria-labelledby") || "";

      // Update IDs and attributes
      const newId = originalId.replace("-0", `-${suffix}`);
      const newLabelledBy = originalLabelledBy.replace("-0", `-${suffix}`);
      const newName = `${element.attr("name") || ""}_${suffix}`;

      element
        .attr("id", newId)
        .attr("aria-labelledby", newLabelledBy)
        .attr("name", newName)
        .attr("data-original", defaultVal)
        .prop("disabled", false);

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
    };

    // Reset input/select fields inside the clone
    multipleClone.find("input, select").each(function () {
      resetInputField($(this), suffix);
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

  // Helper function to clear validation styling from all steps - improved styling
  const clearStepValidationStyles = (template) => {
    $(`.step-navigation-item[data-template="${template}"]`).each(function () {
      const $stepItem = $(this);
      const isActive = $stepItem.hasClass("active");

      // Reset styling with no errors
      styleStepNavItem($stepItem, isActive, false);
    });
  };

  // Helper function to validate all steps with visual feedback
  const validateAllSteps = (template) => {
    const totalSteps = $(
      `.step-navigation-item[data-template="${template}"]`,
    ).length;
    let allValid = true;
    let firstInvalidStep = null;

    // Clear previous validation styles first
    clearStepValidationStyles(template);

    // Validate each step
    for (let step = 1; step <= totalSteps; step++) {
      const stepContainer = getStepContainer(template, step);

      // Validate without focusing (we'll handle focus separately)
      const isStepValid = validateCurrentStepInputs(stepContainer, {
        focusOnError: false,
        markStepInvalid: true,
      });

      if (!isStepValid) {
        allValid = false;
        if (!firstInvalidStep) {
          firstInvalidStep = step;
        }
      }
    }

    // If there are invalid steps, navigate to the first one
    if (!allValid && firstInvalidStep) {
      const targetStepContainer = getStepContainer(template, firstInvalidStep);

      // Navigate to the invalid step
      navigateToStep(template, firstInvalidStep);

      // Now focus on the first invalid input in that step
      setTimeout(() => {
        const firstInvalidInput = targetStepContainer
          .find(".is-invalid")
          .first();
        if (firstInvalidInput.length) {
          const $setting = firstInvalidInput.closest(".col-12");
          highlightSettings($setting);
          firstInvalidInput.focus();
        }
      }, 300); // Slightly longer delay to allow for navigation
    }

    return allValid;
  };

  $(".save-settings").on("click", function () {
    if (isReadOnly) {
      alert(t("alert.readonly_mode"));
      return;
    }

    // For easy mode, validate all steps before saving
    if (currentMode === "easy") {
      const totalSteps = $(
        `.step-navigation-item[data-template="${currentTemplate}"]`,
      ).length;

      // First validate the current step
      const currentStepContainer = getStepContainer(
        currentTemplate,
        currentStep,
      );
      if (!validateCurrentStepInputs(currentStepContainer)) {
        return; // Don't proceed if current step is invalid
      }

      // Then validate all other steps
      let allStepsValid = true;

      for (let step = 1; step <= totalSteps; step++) {
        if (step === currentStep) continue; // Skip current step as it was already validated

        const stepToValidateContainer = getStepContainer(currentTemplate, step);

        if (!validateCurrentStepInputs(stepToValidateContainer)) {
          // Navigate to the invalid step
          navigateToStep(currentTemplate, step);
          allStepsValid = false;
          break;
        }
      }

      if (!allStepsValid) return;
    }

    // For advanced mode, validate all plugin settings before saving
    if (currentMode === "advanced") {
      let allValid = true;
      let firstInvalidPlugin = null;
      let firstInvalidInput = null;

      // Validate all plugin containers
      $("div[id^='navs-plugins-']").each(function () {
        const $pluginContainer = $(this);
        const pluginId = $pluginContainer
          .attr("id")
          .replace("navs-plugins-", "");
        let pluginHasErrors = false;

        // Check all inputs in this plugin
        $pluginContainer.find(".plugin-setting").each(function () {
          const $input = $(this);
          let value = $input.val();
          const isRequired = $input.prop("required");
          const pattern = $input.attr("pattern");
          let $label = $(`label[for="${$input.attr("id")}"]`);
          let fieldName =
            $input.attr("name") || t("validation.default_field_name");

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

          // Check if the field is required and not empty
          if (isRequired && value === "") {
            errorMessage = requiredMessage;
            isValid = false;
          }

          // Validate based on pattern if the input is not empty
          if (isValid && pattern && value !== "") {
            try {
              const regex = new RegExp(pattern);
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
              errorMessage = t("validation.pattern", { field: fieldName });
              isValid = false;
            }
          }

          // Toggle valid/invalid classes
          $input.toggleClass("is-invalid", !isValid);

          // Manage the invalid-feedback element
          let $feedback = $input.next(".invalid-feedback");
          if (!$feedback.length) {
            $feedback = $('<div class="invalid-feedback"></div>').insertAfter(
              $input,
            );
          }

          if (!isValid) {
            $feedback.text(errorMessage);
            allValid = false;
            pluginHasErrors = true;

            // Store the first invalid input for focusing later
            if (!firstInvalidInput) {
              firstInvalidInput = $input;
              firstInvalidPlugin = pluginId;
            }
          } else {
            $feedback.text("");
          }
        });
      });

      // If validation failed, navigate to the first invalid plugin and focus on the error
      if (!allValid && firstInvalidPlugin && firstInvalidInput) {
        // Navigate to the plugin with the first error
        const $targetPlugin = $(
          `.plugin-navigation-item[data-plugin='${firstInvalidPlugin}']`,
        );
        if ($targetPlugin.length) {
          $targetPlugin.trigger("click");

          // After navigation, highlight and focus the invalid input
          setTimeout(() => {
            const $setting = firstInvalidInput.closest(".col-12");
            highlightSettings($setting);
            firstInvalidInput.focus();
          }, 300);
        }

        return; // Don't proceed with saving if validation fails
      }
    }

    // If all validations pass, submit the form
    const form = getFormFromSettings($(this));

    if (currentMode === "raw") {
      // Raw mode validation logic
      const draftInput = $("#is-draft");
      const wasDraft = draftInput.data("original") === "yes";
      const isDraft = form.find("input[name='IS_DRAFT']").val() === "yes";

      if (form.children().length < 2 && isDraft === wasDraft) {
        alert(t("alert.no_changes_detected"));
        return;
      }
    }

    form.appendTo("body").submit();
  });

  $(".toggle-draft").on("click", function () {
    const draftInput = $("#is-draft");
    const isDraft = draftInput.val() === "yes";

    draftInput.val(isDraft ? "no" : "yes");
    const newStatusKey = isDraft ? "status.online" : "status.draft";
    $(".toggle-draft").html(
      `<i class="bx bx-sm bx-${
        isDraft ? "globe" : "file-blank"
      }"></i>&nbsp; <span data-i18n="${newStatusKey}">${t(newStatusKey)}</span>`,
    );
  });

  $(".copy-settings").on("click", function () {
    const config = $("#raw-config").val();

    // Use the Clipboard API
    navigator.clipboard
      .writeText(config)
      .then(() => {
        // Show tooltip
        const button = $(this);
        button
          .attr("data-bs-original-title", t("tooltip.copied"))
          .tooltip("show");

        // Hide tooltip after 2 seconds
        setTimeout(() => {
          button.tooltip("hide").attr("data-bs-original-title", "");
        }, 2000);
      })
      .catch((err) => {
        console.error("Failed to copy text: ", err);
      });
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
      url: `${window.location.pathname
        .split("/")
        .slice(0, -2)
        .join("/")}/global-config?as_json=true`,
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
            } else if ($input.hasClass("multivalue-hidden-input")) {
              const $container = $input.closest(".multivalue-container");
              const separator = $container.data("separator") || " ";
              const values = settingValue
                ? settingValue.split(separator)
                : [""];
              $container.find(".multivalue-input-group").remove();
              $container.find(".multivalue-toggle").remove();

              const $inputsContainer = $container.find(".multivalue-inputs");
              values.forEach((value, index) => {
                const inputGroupHtml = `
                  <div class="input-group mb-2 multivalue-input-group">
                    <input type="text"
                           class="form-control multivalue-input"
                           value="${value.trim()}">
                    <button type="button"
                            class="btn btn-outline-success add-multivalue-item">
                      <i class="bx bx-plus"></i>
                    </button>
                    ${
                      index > 0 || values.length > 1
                        ? `
                    <button type="button"
                            class="btn btn-outline-danger remove-multivalue-item">
                      <i class="bx bx-x"></i>
                    </button>
                    `
                        : ""
                    }
                  </div>
                `;
                $inputsContainer.append(inputGroupHtml);
              });
              updateMultivalueHiddenInput($container);
            } else if (
              $input.is('input[type="hidden"]') &&
              $input.closest(".dropdown").find(".multiselect-toggle").length
            ) {
              $input.val(settingValue).trigger("input");
              const selectedValues = settingValue
                ? settingValue.split(" ")
                : [];
              const $dropdown = $input.closest(".dropdown");
              $dropdown.find(".form-check-input").each(function () {
                const $checkbox = $(this);
                const checkboxVal = $checkbox.val();
                $checkbox.prop("checked", selectedValues.includes(checkboxVal));
              });
              const selectedCount = selectedValues.filter((v) => v).length;
              const $label = $dropdown.find(".multiselect-toggle label");
              $label.text(`(${selectedCount} selected)`);
            } else {
              // Handle simple text-like inputs and textareas
              $input.val(settingValue).trigger("input");
            }
          }
        }

        const feedbackToast = $("#feedback-toast").clone();
        feedbackToast.attr("id", `feedback-toast-${toastNum++}`);
        feedbackToast.find("span").text("Success");
        feedbackToast
          .find(".fw-medium")
          .text("Global settings applied")
          .attr("data-i18n", "toast.global_settings_applied_title");
        feedbackToast
          .find("div.toast-body")
          .text(
            "Global settings have been successfully fetched and applied to the current form.",
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
        feedbackToast.find("span").text("Error");
        feedbackToast
          .find(".fw-medium")
          .text("Failed to fetch global settings")
          .attr("data-i18n", "toast.global_settings_failed_title");
        feedbackToast
          .find("div.toast-body")
          .text("An error occurred while fetching global settings.")
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

  if (
    (usedTemplate === "" || usedTemplate === "ui") &&
    currentMode === "easy"
  ) {
    $('button[data-bs-target="#navs-modes-advanced"]').tab("show");
  } else if (usedTemplate !== "low" && currentMode === "easy") {
    showTemplateTab(usedTemplate);
  } else {
    const $currentTemplateButton = getTemplateTabButton(currentTemplate);
    if (
      $currentTemplateButton.length &&
      !$currentTemplateButton.hasClass("active")
    ) {
      showTemplateTab(currentTemplate);
    }
  }

  var hasExternalPlugins = false;
  var hasProPlugins = false;
  $pluginItems.each(function () {
    const type = $(this).data("type");
    if (type === "external") {
      hasExternalPlugins = true;
    } else if (type === "pro") {
      hasProPlugins = true;
    }
  });

  if (!hasExternalPlugins && !hasProPlugins) {
    $pluginTypeSelect.parent().remove();
  } else if (!hasExternalPlugins) {
    $("#plugin-type-select option[value='external']").remove();
  } else if (!hasProPlugins) {
    $("#plugin-type-select option[value='pro']").remove();
  }

  const hash = window.location.hash;
  if (hash) {
    const targetTab = $(
      `button[data-bs-target="#navs-plugins-${hash.substring(1)}"]`,
    );
    if (targetTab.length) targetTab.tab("show");
  }

  if (currentType !== "all") {
    $pluginTypeSelect.trigger("change");
  }

  if (currentMode === "advanced") {
    const serverNameSetting = $("#setting-general-server-name");
    if (serverNameSetting.val() === "") {
      if (currentType !== "all") {
        currentType = "all";
        $pluginTypeSelect.val("all");
      } else
        $(`button[data-bs-target="#navs-plugins-${currentPlugin}"]`).tab(
          "show",
        );

      if (currentPlugin !== "general") {
        $(`button[data-bs-target="#navs-plugins-general"]`).tab("show");
      }

      updateUrlParams({ type: null });

      highlightSettings(serverNameSetting.closest(".col-12"));
      serverNameSetting.focus();
    }
  }

  if ($serviceMethodInput.length) {
    if ($serviceMethodInput.val() === "autoconf") {
      const feedbackToast = $("#feedback-toast").clone(); // Clone the feedback toast
      feedbackToast.attr("id", `feedback-toast-${toastNum++}`); // Corrected to set the ID for the failed toast
      feedbackToast.find("span").text("Disclaimer");
      feedbackToast
        .find(".fw-medium")
        .text(t("toast.disclaimer_title"))
        .attr("data-i18n", "toast.disclaimer_title");
      feedbackToast
        .find("div.toast-body")
        .html(
          `<div class='fw-bolder' data-i18n="toast.autoconf_disclaimer_bold">${t(
            "toast.autoconf_disclaimer_bold",
          )}</div><span data-i18n="toast.autoconf_disclaimer_detail">${t(
            "toast.autoconf_disclaimer_detail",
          )}</span>`,
        );
      feedbackToast.attr("data-bs-autohide", "false");
      feedbackToast.appendTo("#feedback-toast-container"); // Ensure the toast is appended to the container
      feedbackToast.toast("show");
    }
  }

  var editors = [];

  $(".ace-editor").each(function () {
    const initialContent = $(this).text().trim();
    const editor = ace.edit(this);

    editor.session.setMode("ace/mode/nginx");
    // const language = $(this).data("language"); // TODO: Support ModSecurity
    // if (language === "NGINX") {
    //   editor.session.setMode("ace/mode/nginx");
    // } else {
    //   editor.session.setMode("ace/mode/text"); // Default mode if language is unrecognized
    // }

    const method = $(this).data("method");
    if (method !== "ui" && method !== "default") {
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

    editor.renderer.setScrollMargin(10, 10);
    editors.push(editor);
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

  $(document).on("keydown", ".plugin-setting", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      $(".save-settings").trigger("click");
    }
  });

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

    // After fade-out completes, switch the active panes
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
    } else if ($settingField.hasClass("multivalue-hidden-input")) {
      // Handle multivalue reset
      const $container = $settingField.closest(".multivalue-container");
      const separator = $container.data("separator") || " ";
      const values = valueToSet ? valueToSet.split(separator) : [""]; // Clear existing inputs and toggle
      $container.find(".multivalue-input-group").remove();
      $container.find(".multivalue-toggle").remove();

      // Add inputs for each value
      const $inputsContainer = $container.find(".multivalue-inputs");
      values.forEach((value, index) => {
        const inputGroupHtml = `
          <div class="input-group mb-2 multivalue-input-group">
            <input type="text"
                   class="form-control multivalue-input"
                   value="${value.trim()}">

            <button type="button"
                    class="btn btn-outline-success add-multivalue-item">
              <i class="bx bx-plus"></i>
            </button>

            ${
              index > 0 || values.length > 1
                ? `
            <button type="button"
                    class="btn btn-outline-danger remove-multivalue-item">
              <i class="bx bx-x"></i>
            </button>
            `
                : ""
            }
          </div>
        `;
        $inputsContainer.append(inputGroupHtml);
      });

      updateMultivalueHiddenInput($container);
    } else {
      $settingField.val(valueToSet).trigger("input");
    }

    // Highlight the field to indicate it's been reset
    const $setting = $settingField.closest(".col-12");
    highlightSettings($setting);
  });

  isInit = false;

  // Multivalue functionality
  const updateMultivalueLabels = ($container) => {
    const $hiddenInput = $container.find(".multivalue-hidden-input");
    const settingName = $hiddenInput.attr("name");
    const baseId = $hiddenInput.attr("id");

    $container.find(".multivalue-input-group").each(function (index) {
      const $group = $(this);
      const $input = $group.find(".multivalue-input");
      const $label = $group.find("label");
      const newIndex = index + 1;
      const newId = `${baseId}_${newIndex}`;

      $input.attr("id", newId);

      // First item has no index, subsequent items have #1, #2, etc.
      if (index === 0) {
        $label.attr("for", newId).text(settingName);
      } else {
        $label.attr("for", newId).text(`${settingName} #${index}`);
      }
    });
  };

  const updateMultivalueFloatingLabel = ($container) => {
    // Update floating label state for each input based on its value
    $container.find(".multivalue-input-group").each(function () {
      const $inputGroup = $(this);
      const $input = $inputGroup.find(".multivalue-input");
      const hasValue = $input.val().trim() !== "";

      if (hasValue) {
        $inputGroup.addClass("has-value");
      } else {
        $inputGroup.removeClass("has-value");
      }
    });
  };

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
          <button type="button" class="btn btn-sm btn-outline-secondary multivalue-toggle-btn">
            <i class="bx bx-chevron-down me-1"></i>
            <span class="toggle-text">Show all (<span class="hidden-count">${
              $inputGroups.length - visibleLimit
            }</span> more)</span>
          </button>
        </div>
      `;
      $container.find(".multivalue-inputs").after(toggleHtml);
      $toggle = $container.find(".multivalue-toggle");
    } else {
      // Update count
      $toggle.find(".hidden-count").text($inputGroups.length - visibleLimit);
    }

    const $toggleBtn = $container.find(".multivalue-toggle-btn");
    const $toggleText = $container.find(".toggle-text");
    let isExpanded = $toggleBtn.hasClass("expanded");

    if (isToggleAction) {
      isExpanded = !isExpanded;
      $toggleBtn.toggleClass("expanded", isExpanded);
    }

    if (isExpanded) {
      $inputGroups.show();
      $toggleText.text("Show less");
      $toggleBtn
        .find("i")
        .removeClass("bx-chevron-down")
        .addClass("bx-chevron-up");
    } else {
      $inputGroups.slice(visibleLimit).hide();
      $toggleText.html(
        `Show all (<span class="hidden-count">${
          $inputGroups.length - visibleLimit
        }</span> more)`,
      );
      $toggleBtn
        .find("i")
        .removeClass("bx-chevron-up")
        .addClass("bx-chevron-down");
    }
  };

  const updateMultivalueHiddenInput = ($container) => {
    const separator = $container.data("separator") || " ";
    const $hiddenInput = $container.find(".multivalue-hidden-input");
    const values = [];

    $container.find(".multivalue-input").each(function () {
      const value = $(this).val().trim();
      if (value) {
        values.push(value);
      }
    });

    $hiddenInput.val(values.join(separator));
    $hiddenInput.trigger("change");
  };

  const addMultivalueItem = ($container, value = "", $insertAfter = null) => {
    const isDisabled = $container
      .find(".multivalue-hidden-input")
      .prop("disabled");

    if (isDisabled) return;

    // Get the base ID and setting name from the hidden input
    const $hiddenInput = $container.find(".multivalue-hidden-input");
    const baseId = $hiddenInput.attr("id");
    const settingName = $hiddenInput.attr("name");

    // Calculate the index for the new input
    const currentCount = $container.find(".multivalue-input-group").length;
    const newIndex = currentCount + 1;
    const inputId = `${baseId}_${newIndex}`;

    const inputGroupHtml = `
      <div class="form-floating multivalue-input-group">
        <div class="input-group">
          <input type="text"
                 class="form-control multivalue-input"
                 value="${value}"
                 id="${inputId}">
          <button type="button"
                  class="btn btn-outline-success add-multivalue-item">
            <i class="bx bx-plus"></i>
          </button>
          <button type="button"
                  class="btn btn-outline-danger remove-multivalue-item">
            <i class="bx bx-x"></i>
          </button>
        </div>
        <label for="${inputId}" class="text-truncate">Temporary</label>
      </div>
    `;

    if ($insertAfter && $insertAfter.length) {
      $insertAfter.after(inputGroupHtml);
    } else {
      const $inputsContainer = $container.find(".multivalue-inputs");
      $inputsContainer.append(inputGroupHtml);
    }

    // Update margin bottom for all input groups
    const $allGroups = $container.find(".multivalue-input-group");
    $allGroups.removeClass("mb-2");
    $allGroups.not(":last").addClass("mb-2");

    // Update all labels with correct indices
    updateMultivalueLabels($container);

    const $newInput = $container.find(".multivalue-input").last();
    $newInput.focus();

    // Update floating label behavior when new input is added
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

    // Update margin bottom for remaining input groups
    const $allGroups = $container.find(".multivalue-input-group");
    $allGroups.removeClass("mb-2");
    $allGroups.not(":last").addClass("mb-2");

    // Update all labels with correct indices
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

  // Initialize existing multivalue containers
  $(".multivalue-container").each(function () {
    const $container = $(this);
    updateMultivalueHiddenInput($container);
    updateMultivalueFloatingLabel($container);
    toggleMultivalueVisibility($container, false);
  });

  // Handle multivalue toggle button clicks
  $(document).on("click", ".multivalue-toggle-btn", function () {
    const $container = $(this).closest(".multivalue-container");
    toggleMultivalueVisibility($container, true);
  });

  // Handle add button clicks
  $(document).on("click", ".add-multivalue-item", function () {
    const $container = $(this).closest(".multivalue-container");
    const $currentInputGroup = $(this).closest(".multivalue-input-group");
    addMultivalueItem($container, "", $currentInputGroup);
  });

  // Handle remove button clicks
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

  // Handle focus/blur for floating label behavior
  $(document).on("focus blur", ".multivalue-input", function () {
    const $container = $(this).closest(".multivalue-container");
    updateMultivalueFloatingLabel($container);
  }); // Handle Enter key in multivalue inputs to add new item
  $(document).on("keydown", ".multivalue-input", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      const $container = $(this).closest(".multivalue-container");
      const $currentInputGroup = $(this).closest(".multivalue-input-group");
      const currentValue = $(this).val().trim();

      if (currentValue) {
        addMultivalueItem($container, "", $currentInputGroup);
      }
    }
  });

  // Multiselect dropdown functionality
  const updateMultiselectDisplay = ($dropdown) => {
    const $toggle = $dropdown.find(".multiselect-toggle");
    const $label = $toggle.find("label");
    const $checkboxes = $dropdown.find('input[type="checkbox"]');

    const checkedCheckboxes = $checkboxes.filter(":checked");
    const checkedCount = checkedCheckboxes.length;

    // Update the count in the label
    $label.text(`(${checkedCount} selected)`);

    // Update the hidden value - space-separated list of selected option IDs
    const selectedIds = checkedCheckboxes
      .map(function () {
        return $(this).attr("value"); // Use the option ID from the value attribute
      })
      .get();

    // Find or create hidden input to store the value
    let $hiddenInput = $dropdown.find('input[type="hidden"]');
    if ($hiddenInput.length === 0) {
      const settingName = $toggle.find(".multiselect-text").text();
      $hiddenInput = $(
        `<input type="hidden" name="${settingName}" class="plugin-setting">`,
      );
      $dropdown.append($hiddenInput);
    }

    // Save as space-separated list of option IDs
    $hiddenInput.val(selectedIds.join(" "));

    // Trigger change event for validation
    $hiddenInput.trigger("change");
  };

  // Initialize multiselect dropdowns with custom behavior
  $(".dropdown")
    .has(".multiselect-toggle")
    .each(function () {
      const $dropdown = $(this);
      updateMultiselectDisplay($dropdown);

      // Initialize Bootstrap dropdown with autoClose disabled
      const $toggle = $dropdown.find(".multiselect-toggle");
      if ($toggle.length) {
        new bootstrap.Dropdown($toggle[0], {
          autoClose: false,
        });
      }
    });

  // Handle multiselect toggle button clicks manually
  $(document).on("click", ".multiselect-toggle", function (e) {
    e.preventDefault();
    e.stopPropagation();

    const $dropdown = $(this).closest(".dropdown");
    const $menu = $dropdown.find(".dropdown-menu");
    const isOpen = $dropdown.hasClass("show");

    // Close all other multiselect dropdowns first
    $(".dropdown")
      .has(".multiselect-toggle")
      .not($dropdown)
      .each(function () {
        const $otherDropdown = $(this);
        const $otherMenu = $otherDropdown.find(".dropdown-menu");
        const $otherToggle = $otherDropdown.find(".multiselect-toggle");

        $otherDropdown.removeClass("show");
        $otherMenu.removeClass("show");
        $otherToggle.attr("aria-expanded", "false");
      });

    if (isOpen) {
      // Close this dropdown
      $dropdown.removeClass("show");
      $menu.removeClass("show");
      $(this).attr("aria-expanded", "false");
    } else {
      // Open this dropdown
      $dropdown.addClass("show");
      $menu.addClass("show");
      $(this).attr("aria-expanded", "true");
    }
  });

  // Handle clicks outside multiselect dropdowns to close them
  $(document).on("click", function (e) {
    const $target = $(e.target);

    // Check if click is outside any multiselect dropdown
    $(".dropdown")
      .has(".multiselect-toggle")
      .each(function () {
        const $dropdown = $(this);
        const $menu = $dropdown.find(".dropdown-menu");
        const $toggle = $dropdown.find(".multiselect-toggle");

        // If click is outside this dropdown and it's open, close it
        if (
          !$dropdown.is($target) &&
          $dropdown.has($target).length === 0 &&
          $dropdown.hasClass("show")
        ) {
          $dropdown.removeClass("show");
          $menu.removeClass("show");
          $toggle.attr("aria-expanded", "false");
        }
      });
  });

  // Handle checkbox changes in multiselect dropdowns
  $(document).on("change", '.dropdown input[type="checkbox"]', function () {
    const $dropdown = $(this).closest(".dropdown");
    if ($dropdown.find(".multiselect-toggle").length) {
      updateMultiselectDisplay($dropdown);
    }
  });

  // Handle clicking on dropdown items - toggle checkbox but keep dropdown open
  $(document).on("click", ".dropdown-menu .dropdown-item", function (e) {
    // Only handle if this is a multiselect dropdown
    if ($(this).closest(".dropdown").find(".multiselect-toggle").length) {
      e.stopPropagation(); // Prevent event bubbling

      if (
        !$(e.target).is('input[type="checkbox"]') &&
        !$(e.target).is("label")
      ) {
        const $checkbox = $(this).find('input[type="checkbox"]');
        $checkbox.prop("checked", !$checkbox.prop("checked")).trigger("change");
      }
    }
  });

  // Sidebar plugin navigation: ensure clicking a plugin shows its pane
  $(document).off("click", ".plugin-navigation-item");
  $(document).on("click", ".plugin-navigation-item", function () {
    const plugin = $(this).data("plugin");
    if (!plugin) return;

    // Don't do anything if already active
    if (currentPlugin === plugin) return;

    // Remove active and highlight classes from all navigation items
    $(".plugin-navigation-item")
      .removeClass("active show")
      .attr("aria-selected", "false");

    // Mark this navigation item as active
    $(this).addClass("active show").attr("aria-selected", "true");

    // Smooth scroll the selected plugin into view in the sidebar only
    const sidebarContainer = $("#navs-modes-advanced .step-navigation-list")[0];
    const elementRect = this.getBoundingClientRect();
    const containerRect = sidebarContainer.getBoundingClientRect();

    if (
      elementRect.top < containerRect.top ||
      elementRect.bottom > containerRect.bottom
    ) {
      const scrollTop =
        sidebarContainer.scrollTop +
        (elementRect.top - containerRect.top) -
        containerRect.height / 2 +
        elementRect.height / 2;

      sidebarContainer.scrollTo({
        top: scrollTop,
        behavior: "smooth",
      });
    }

    // Reference all plugin panes and the target pane
    const $allPanes = $("div[id^='navs-plugins-']");
    const $currentPane = $allPanes.filter(".show.active");
    const $nextPane = $(`#navs-plugins-${plugin}`);

    // Ensure all panes except current are fully hidden
    $allPanes.not($currentPane).removeClass("show active").hide();

    // Smooth transition between panes
    if ($currentPane.length && !$currentPane.is($nextPane)) {
      // Ensure transitions complete sequentially
      $currentPane.fadeOut(150, function () {
        // Remove classes after fade-out completes
        $currentPane.removeClass("show active");

        // Prepare the next pane and fade it in
        $nextPane.css("opacity", 0).show();
        $nextPane.addClass("active");

        // Trigger reflow to ensure transitions work properly
        $nextPane[0].offsetHeight;

        $nextPane.animate({ opacity: 1 }, 150, function () {
          $nextPane.addClass("show");
        });
      });
    } else {
      // If no current pane or it's the same pane, just show the target
      $nextPane.css("opacity", 0).show();
      $nextPane.addClass("active");

      // Short delay to ensure proper rendering
      setTimeout(function () {
        $nextPane.animate({ opacity: 1 }, 150, function () {
          $nextPane.addClass("show");
        });
      }, 10);
    }

    // Update global state and URL
    currentPlugin = plugin;
    window.location.hash = plugin;

    // Update visual styling for navigation
    $(".plugin-navigation-item .step-number")
      .removeClass("btn-primary")
      .addClass("btn-outline-primary disabled");
    $(this)
      .find(".step-number")
      .removeClass("btn-outline-primary disabled")
      .addClass("btn-primary");
  });

  // On page load, if hash matches a plugin and mode is advanced, activate that plugin
  if (hash && currentMode === "advanced") {
    const $targetPlugin = $(
      `.plugin-navigation-item[data-plugin='${hash.replace("#", "")}']`,
    );
    if ($targetPlugin.length) {
      $targetPlugin.trigger("click");
      currentPlugin = hash.replace("#", "");
      window.location.hash = hash;

      // Smooth scroll to the plugin in the sidebar only
      const sidebarContainer = $(
        "#navs-modes-advanced .step-navigation-list",
      )[0];
      const elementRect = $targetPlugin[0].getBoundingClientRect();
      const containerRect = sidebarContainer.getBoundingClientRect();

      if (
        elementRect.top < containerRect.top ||
        elementRect.bottom > containerRect.bottom
      ) {
        const scrollTop =
          sidebarContainer.scrollTop +
          (elementRect.top - containerRect.top) -
          containerRect.height / 2 +
          elementRect.height / 2;

        sidebarContainer.scrollTo({
          top: scrollTop,
          behavior: "smooth",
        });
      }
    }
  }

  $("#plugin-keyword-search-top").on(
    "input",
    debounce((e) => {
      const keyword = e.target.value.toLowerCase().trim();
      if (!keyword) return;

      let matchedPlugin = null;
      let matchedSettings = $();

      $("div[id^='navs-plugins-']").each(function () {
        const $plugin = $(this);
        const pluginId = $plugin.attr("id").replace("navs-plugins-", "");
        const pluginType = $plugin.data("type");
        if (currentType !== "all" && pluginType !== currentType) {
          return;
        }

        const matchingSettings = $plugin
          .find("input, select")
          .filter(function () {
            const $this = $(this);
            const settingType = $this.attr("type");
            if (settingType === "hidden") return false;
            const settingName = ($this.attr("name") || "").toLowerCase();
            const label = $this.next("label");
            const labelText = (label.text() || "").toLowerCase();
            return labelText.includes(keyword) || settingName.includes(keyword);
          });

        if (matchingSettings.length > 0) {
          matchedPlugin = pluginId;
          matchedSettings = matchingSettings.closest(".col-12");
          return false;
        }
      });

      if (matchedPlugin) {
        // Only trigger navigation if we're changing plugins
        if (currentPlugin !== matchedPlugin) {
          // Use the existing navigation mechanism to ensure clean transitions
          const $targetPlugin = $(
            `.plugin-navigation-item[data-plugin='${matchedPlugin}']`,
          );

          // Allow previous animations to finish
          setTimeout(() => {
            $targetPlugin.trigger("click");

            // Highlight settings after navigation is complete
            setTimeout(() => {
              if (matchedSettings.length > 0) {
                highlightSettings(matchedSettings, 1000);
              }
            }, 200);
          }, 10);
        } else {
          // If we're already on the correct plugin, just highlight
          if (matchedSettings.length > 0) {
            highlightSettings(matchedSettings, 1000);
          }
        }
      }
    }, 100),
  );
});
