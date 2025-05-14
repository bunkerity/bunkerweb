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

  const $templateInput = $("#used-template");
  let usedTemplate = "low";
  if ($templateInput.length) {
    usedTemplate = $templateInput.val().trim();
  }

  let currentTemplate = $("#selected-template").val();
  let currentMode = $("#selected-mode").val();
  let currentType = $("#selected-type").val();

  const $serviceMethodInput = $("#service-method");
  const $pluginSearch = $("#plugin-search");
  const $pluginTypeSelect = $("#plugin-type-select");
  const $pluginKeywordSearch = $("#plugin-keyword-search");
  const $pluginDropdownMenu = $("#plugins-dropdown-menu");
  const $pluginDropdownItems = $("#plugins-dropdown-menu li.nav-item");
  const $templateSearch = $("#template-search");
  const $templateDropdownMenu = $("#templates-dropdown-menu");
  const $templateDropdownItems = $("#templates-dropdown-menu li.nav-item");

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

    newUrl.search = searchParams.toString();
    if (removeHash) {
      newUrl.hash = "";
    }

    history.pushState(params, document.title, newUrl.toString());
  };

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

  const resetTemplateConfig = () => {
    const templateContainer = $(`#navs-templates-${currentTemplate}`);
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
        `.step-navigation-item[data-step="1"][data-template="${currentTemplate}"]`,
      );
      if (firstStep.length) {
        // Set currentStep to ensure proper navigation
        currentStep = 1;

        // Update UI state - properly managing show/active classes
        $(`.step-navigation-item[data-template="${currentTemplate}"]`).each(
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
        const $activePanes = $(
          `#navs-templates-${currentTemplate} .template-steps-content .tab-pane.active`,
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
        $(`#navs-templates-${currentTemplate} .previous-step`).addClass(
          "disabled",
        );
        $(`#navs-templates-${currentTemplate} .next-step`).removeClass(
          "disabled",
        );
      }
    }, 100);
  };

  // Enhanced handleTabChange function with validation check
  const handleTabChange = (targetClass) => {
    // If we're changing templates in easy mode, validate current step first
    if (
      targetClass.includes("navs-templates-") &&
      currentMode === "easy" &&
      !isInit
    ) {
      const currentStepId = `navs-steps-${currentTemplate}-${currentStep}`;
      const currentStepContainer = $(`#${currentStepId}`);

      // Only proceed if validation passes
      if (!validateCurrentStepInputs(currentStepContainer)) {
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
      params.template = null; // Remove the template parameter

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
      if (!isInit) resetTemplateConfig();
      setTimeout(() => {
        currentTemplate = targetClass
          .substring(1)
          .replace("navs-templates-", "");

        params.type = null; // Remove the type parameter

        // If "low"  is selected, remove the "template" parameter
        if (currentTemplate === "low") {
          params.template = null; // Set template to null to remove it from the URL
          updateUrlParams(params); // Call the function without the hash (keep it intact)
        } else {
          // If another template is selected, update the "template" parameter
          params.template = currentTemplate;
          updateUrlParams(params); // Keep the template in the URL
        }
      }, 200);
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
    const { focusOnError = true, markStepInvalid = true } = options;
    let isStepValid = true;
    let firstInvalidInput = null;

    // Get step number and template from container
    const stepNumber = currentStepContainer.data("step");
    const template = currentStepContainer.attr("id").split("-")[2]; // Extract template name

    // Find the nav item for this step
    const $navItem = $(
      `.step-navigation-item[data-step="${stepNumber}"][data-template="${template}"]`,
    );

    // Count of invalid fields to track
    let invalidFieldsCount = 0;

    currentStepContainer.find(".plugin-setting").each(function () {
      const $input = $(this);
      const value = $input.val();
      const isRequired = $input.prop("required");
      const pattern = $input.attr("pattern");
      const $label = $(`label[for="${$input.attr("id")}"]`);
      let fieldName = $input.attr("name") || t("validation.default_field_name");

      if ($label.length) {
        const i18nKey = $label.attr("data-i18n");
        const labelText = $label
          .text()
          .trim()
          .replace(/\(optional\)$/i, "")
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

        // Check if it's a multiple setting with numeric suffix
        const isMultipleSetting =
          settingName &&
          $this.attr("id").startsWith("multiple-") &&
          /_\d+$/.test(settingName);

        appendHiddenInput(form, settingName, settingValue);
      });
    };

    // Handle missing CSRF token gracefully
    const csrfToken = $("#csrf_token").val() || "";
    appendHiddenInput(form, "csrf_token", csrfToken);

    if (currentMode === "easy") {
      appendHiddenInput(form, "USE_TEMPLATE", currentTemplate);

      const templateContainer = $(`#navs-templates-${currentTemplate}`);
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

  $("#select-plugin").on("click", () => $pluginSearch.focus());

  $pluginSearch.on(
    "input",
    debounce((e) => {
      const inputValue = e.target.value.toLowerCase();
      let visibleItems = 0;

      $pluginDropdownItems.each(function () {
        const item = $(this);
        const matches =
          (currentType === "all" || item.data("type") === currentType) &&
          (item.text().toLowerCase().includes(inputValue) ||
            item.find("button").data("bs-target").includes(inputValue));

        item.toggle(matches);

        if (matches) {
          visibleItems++; // Increment when an item is shown
        }
      });

      if (visibleItems === 0) {
        if ($pluginDropdownMenu.find(".no-plugin-items").length === 0) {
          $pluginDropdownMenu.append(
            `<li class="no-plugin-items dropdown-item text-muted">${t(
              "status.no_item",
            )}</li>`,
          );
        }
      } else {
        $pluginDropdownMenu.find(".no-plugin-items").remove();
      }
    }, 50),
  );

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

  $(document).on("hidden.bs.dropdown", "#select-plugin", function () {
    $("#plugin-search").val("").trigger("input");
  });

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
      const currentStepId = `navs-steps-${currentTemplate}-${currentStep}`;
      const currentStepContainer = $(`#${currentStepId}`);

      if (!validateCurrentStepInputs(currentStepContainer)) {
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
      const currentStepId = `navs-steps-${currentTemplate}-${currentStep}`;
      const currentStepContainer = $(`#${currentStepId}`);

      if (!validateCurrentStepInputs(currentStepContainer)) {
        e.preventDefault(); // Prevent tab change
        e.stopPropagation(); // Stop event bubbling
        return false;
      }
    },
  );

  $('#templates-dropdown-menu button[data-bs-toggle="tab"]').on(
    "shown.bs.tab",
    (e) => {
      if (!handleTabChange($(e.target).data("bs-target"))) {
        // If handleTabChange returns false, revert to the previous tab
        $(`button[data-bs-target="#navs-templates-${currentTemplate}"]`).tab(
          "show",
        );
      }
    },
  );

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
        const currentStepId = `navs-steps-${currentTemplate}-${currentStep}`;
        const currentStepContainer = $(`#${currentStepId}`);

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

  $pluginTypeSelect.on("change", function () {
    currentType = $(this).val();
    const params =
      currentType === "all" ? { type: null } : { type: currentType };

    updateUrlParams(params);

    $pluginDropdownItems.each(function () {
      const typeMatches =
        currentType === "all" || $(this).data("type") === currentType;
      $(this).toggle(typeMatches);
    });

    const currentPane = $('div[id^="navs-plugins-"].active').first();
    if (currentPane.data("type") !== currentType) {
      $(`#plugins-dropdown-menu li.nav-item[data-type="${currentType}"]`)
        .first()
        .find("button")
        .tab("show");
    }
  });

  $pluginKeywordSearch.on(
    "input",
    debounce((e) => {
      const keyword = e.target.value.toLowerCase().trim();
      if (!keyword) return;

      let matchedPlugin = null;
      let matchedSettings = $();

      $("div[id^='navs-plugins-']").each(function () {
        const $plugin = $(this);
        const pluginId = $plugin.attr("id").replace("navs-plugins-", "");
        const pluginType = $plugin.data("type"); // Get the type of the plugin (core, external, pro)

        // If the currentType filter is not "all" and the plugin's type doesn't match the currentType, skip this plugin
        if (currentType !== "all" && pluginType !== currentType) {
          return; // Skip this plugin
        }

        // Find settings that match the keyword based on label text or input/select name
        const matchingSettings = $plugin
          .find("input, select")
          .filter(function () {
            const $this = $(this);
            const settingType = $this.attr("type");

            if (settingType === "hidden") return false;

            const settingName = ($this.attr("name") || "").toLowerCase();
            const label = $this.next("label");
            const labelText = (label.text() || "").toLowerCase();

            // Match either the label text or the input/select name
            return labelText.includes(keyword) || settingName.includes(keyword);
          });

        if (matchingSettings.length > 0) {
          matchedPlugin = pluginId;
          matchedSettings = matchingSettings.closest(".col-12");
          return false; // Stop searching after finding a plugin with matching settings
        }
      });

      if (matchedPlugin) {
        // Automatically switch to the plugin tab
        $(`button[data-bs-target="#navs-plugins-${matchedPlugin}"]`).tab(
          "show",
        );

        // Highlight all matched settings
        if (matchedSettings.length > 0) {
          highlightSettings(matchedSettings, 1000);
        }
      }
    }, 100),
  );

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
      const stepId = `navs-steps-${template}-${step}`;
      const stepContainer = $(`#${stepId}`);

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
      const targetStepId = `navs-steps-${template}-${firstInvalidStep}`;
      const targetStepContainer = $(`#${targetStepId}`);

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
      const currentStepId = `navs-steps-${currentTemplate}-${currentStep}`;
      const currentStepContainer = $(`#${currentStepId}`);
      if (!validateCurrentStepInputs(currentStepContainer)) {
        return; // Don't proceed if current step is invalid
      }

      // Then validate all other steps
      let allStepsValid = true;

      for (let step = 1; step <= totalSteps; step++) {
        if (step === currentStep) continue; // Skip current step as it was already validated

        const stepToValidateId = `navs-steps-${currentTemplate}-${step}`;
        const stepToValidateContainer = $(`#${stepToValidateId}`);

        if (!validateCurrentStepInputs(stepToValidateContainer)) {
          // Navigate to the invalid step
          navigateToStep(currentTemplate, step);
          allStepsValid = false;
          break;
        }
      }

      if (!allStepsValid) return;
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
      }"></i>&nbsp; <span data-i18n="${newStatusKey}">${t(
        newStatusKey,
      )}</span>`,
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

  $(document).on("click", ".next-step, .previous-step", function () {
    const isNext = $(this).hasClass("next-step");
    const template = $(this).data("template");

    // Determine the new step
    const newStep = isNext ? currentStep + 1 : currentStep - 1;

    // Validate current step if going forward
    if (isNext) {
      const currentStepId = `navs-steps-${template}-${currentStep}`;
      const currentStepContainer = $(`#${currentStepId}`);
      const isStepValid = validateCurrentStepInputs(currentStepContainer);

      if (!isStepValid) {
        // Prevent proceeding to the next step
        return;
      }
    }

    // Trigger click on the target step navigation item
    $(
      `.step-navigation-item[data-step="${newStep}"][data-template="${template}"]`,
    ).trigger("click");
  });

  // Update the step navigation item click handler to manage button states
  $(document).on("click", ".step-navigation-item", function () {
    const targetStep = parseInt($(this).data("step"));
    const template = $(this).data("template");
    const stepId = $(this).data("step-id");

    // Don't proceed if already on this step
    if (targetStep === currentStep) return;

    // If trying to navigate to a future step, validate current step first
    if (targetStep > currentStep) {
      const currentStepId = `navs-steps-${template}-${currentStep}`;
      const currentStepContainer = $(`#${currentStepId}`);
      const isStepValid = validateCurrentStepInputs(currentStepContainer);

      if (!isStepValid) {
        // Prevent navigation if validation fails
        return;
      }

      // Validate all steps between current and target
      for (let step = currentStep + 1; step < targetStep; step++) {
        const stepToValidateId = `navs-steps-${template}-${step}`;
        const stepToValidateContainer = $(`#${stepToValidateId}`);
        if (!validateCurrentStepInputs(stepToValidateContainer)) {
          // Show the invalid step instead of the requested one
          $(
            `.step-navigation-item[data-step="${step}"][data-template="${template}"]`,
          ).trigger("click");
          return;
        }
      }
    }

    // Update active state in step navigation
    $(`.step-navigation-item[data-template="${template}"]`).removeClass(
      "active",
    );
    $(`.step-navigation-item[data-template="${template}"] .step-number`)
      .addClass("disabled btn-outline-primary")
      .removeClass("btn-primary");
    $(`.step-navigation-item[data-template="${template}"] .fw-bold`)
      .removeClass("text-primary")
      .addClass("text-muted");

    $(this).addClass("active");
    $(this).find(".step-number").removeClass("disabled");
    $(this).find(".fw-bold").removeClass("text-muted").addClass("text-primary");

    // Update currentStep
    currentStep = targetStep;

    // Handle tab pane display - properly using Bootstrap's fade functionality
    // First hide all step panes
    $(
      `#navs-templates-${template} .template-steps-content .tab-pane`,
    ).removeClass("show active");

    // Then show the target step pane
    $(`#${stepId}`).addClass("show active");

    // Update previous/next button states
    const totalSteps = $(
      `.step-navigation-item[data-template="${template}"]`,
    ).length;
    const $previousBtn = $(`#navs-templates-${template}`).find(
      ".previous-step",
    );
    const $nextBtn = $(`#navs-templates-${template}`).find(".next-step");

    $previousBtn.toggleClass("disabled", currentStep === 1);
    $nextBtn.toggleClass("disabled", currentStep === totalSteps);

    // Scroll the step content into view
    $(`#${stepId}`)[0].scrollIntoView({ behavior: "smooth", block: "start" });
  });

  // Simplify the next/previous step handlers - they should just trigger the appropriate step navigation item
  $(document).on("click", ".next-step, .previous-step", function () {
    if ($(this).hasClass("disabled")) return; // Don't do anything if button is disabled

    const isNext = $(this).hasClass("next-step");
    const template = $(this).data("template");

    // Determine the new step
    const newStep = isNext ? currentStep + 1 : currentStep - 1;

    // Validate current step if going forward
    if (isNext) {
      const currentStepId = `navs-steps-${template}-${currentStep}`;
      const currentStepContainer = $(`#${currentStepId}`);
      const isStepValid = validateCurrentStepInputs(currentStepContainer);

      if (!isStepValid) {
        // Prevent proceeding to the next step
        return;
      }
    }

    // Find and trigger click on the target step navigation item
    const $targetStepItem = $(
      `.step-navigation-item[data-step="${newStep}"][data-template="${template}"]`,
    );
    if ($targetStepItem.length) {
      $targetStepItem.trigger("click");
    }
  });

  $("#reset-template-config").on("click", function () {
    const reset_modal = $("#modal-reset-template-config");
    reset_modal.modal("show");
  });

  $("#confirm-reset-template-config").on("click", function () {
    resetTemplateConfig();
  });

  $('div[id^="multiple-"]')
    .filter(function () {
      return /^multiple-.*-\d+$/.test($(this).attr("id"));
    })
    .each(function () {
      let defaultValues = true;
      let disabled = false;
      $(this)
        .find("input, select")
        .each(function () {
          const type = $(this).attr("type");
          const defaultVal = $(this).data("default");

          if ($(this).prop("disabled")) {
            disabled = true;
          }

          // Check for select element
          if ($(this).is("select")) {
            const selectedVal = $(this).find("option:selected").val();
            if (selectedVal != defaultVal) {
              defaultValues = false;
            }
          } else if (type === "checkbox") {
            const isChecked =
              $(this).prop("checked") === (defaultVal === "yes");
            if (!isChecked) {
              defaultValues = false;
            }
          } else {
            const isMatchingValue = $(this).val() == defaultVal;
            if (!isMatchingValue) {
              defaultValues = false;
            }
          }
        });

      if (defaultValues) $(`#show-${$(this).attr("id")}`).trigger("click");
      if (disabled && $(`#remove-${$(this).attr("id")}`).length) {
        $(`#remove-${$(this).attr("id")}`).addClass("disabled");
        $(`#remove-${$(this).attr("id")}`)
          .parent()
          .attr("title", t("tooltip.cannot_remove_disabled"));

        new bootstrap.Tooltip(
          $(`#remove-${$(this).attr("id")}`)
            .parent()
            .get(0),
          {
            placement: "top",
          },
        );
      }
    });

  if (
    (usedTemplate === "" || usedTemplate === "ui") &&
    currentMode === "easy"
  ) {
    $('button[data-bs-target="#navs-modes-advanced"]').tab("show");
  } else if (usedTemplate !== "low" && currentMode === "easy") {
    $(`button[data-bs-target="#navs-templates-${usedTemplate}"]`).tab("show");
  } else if (
    !$(`button[data-bs-target="#navs-templates-${currentTemplate}"]`).hasClass(
      "active",
    )
  ) {
    $(`button[data-bs-target="#navs-templates-${currentTemplate}"]`).tab(
      "show",
    );
  }

  var hasExternalPlugins = false;
  var hasProPlugins = false;
  $pluginDropdownItems.each(function () {
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
    if (method !== "ui") {
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

  // Remove all previously attached handlers to avoid duplication
  $(document).off("click", ".step-navigation-item");
  $(document).off("click", ".next-step, .previous-step");

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

    const stepId = $targetStepItem.data("step-id");

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
    const $currentPane = $(
      `#navs-templates-${template} .template-steps-content .tab-pane.active`,
    );
    const $targetPane = $(`#${stepId}`);

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
    const $previousBtn = $(`#navs-templates-${template} .previous-step`);
    const $nextBtn = $(`#navs-templates-${template} .next-step`);

    $previousBtn.toggleClass("disabled", targetStep === 1);
    $nextBtn.toggleClass("disabled", targetStep === totalSteps);

    // Scroll into view after transition is complete
    setTimeout(() => {
      $(`#${stepId}`)[0].scrollIntoView({ behavior: "smooth", block: "start" });
    }, 350); // Give enough time for the fade-in to complete
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

      // Skip action if button is disabled
      if ((isNextButton || isPrevButton) && $(this).hasClass("disabled")) {
        return;
      }

      // Get template and determine target step
      let template, targetStep;

      if (isDirectStepClick) {
        targetStep = parseInt($(this).data("step"));
        template = $(this).data("template");

        // Don't proceed if already on this step
        if (targetStep === currentStep) return;
      } else {
        template = $(this).data("template");
        targetStep = isNextButton ? currentStep + 1 : currentStep - 1;
      }

      // Always validate current step to update its validation state
      // regardless of whether we're going forward or backward
      const currentStepId = `navs-steps-${template}-${currentStep}`;
      const currentStepContainer = $(`#${currentStepId}`);

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
      const template = stepContainer.attr("id").split("-")[2];
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

    // Find the associated input/select/checkbox
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
    } else {
      $settingField.val(valueToSet).trigger("input");
    }

    // Highlight the field to indicate it's been reset
    const $setting = $settingField.closest(".col-12");
    highlightSettings($setting);
  });

  isInit = false;
});
