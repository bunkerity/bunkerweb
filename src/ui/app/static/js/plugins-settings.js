$(document).ready(() => {
  let currentPlugin = "general";
  let currentMode = "easy";
  let currentType = "all";
  let currentKeywords = "";

  const $pluginSearch = $("#plugin-search");
  const $pluginTypeSelect = $("#plugin-type-select");
  const $pluginDropdownMenu = $("#plugins-dropdown-menu");
  const pluginDropdownItems = $("#plugins-dropdown-menu li.nav-item");

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
    if (currentType !== "all") params.type = currentType;

    // If "easy" is selected, remove the "mode" parameter
    if (currentMode === "easy") {
      params.mode = null; // Set mode to null to remove it from the URL
      updateUrlParams(params); // Call the function without the hash (keep it intact)
    } else {
      // If another mode is selected, update the "mode" parameter
      params.mode = currentMode;
      updateUrlParams(params); // Keep the mode in the URL
    }
  };

  const handleTabChange = (targetClass) => {
    currentPlugin = targetClass.substring(1).replace("navs-plugins-", "");

    // Prepare the params for URL (parameters to be updated in the URL)
    const params = {};
    if (currentType !== "all") params.type = currentType;
    if (currentMode !== "easy") params.mode = currentMode;

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
  };

  const debounce = (func, delay) => {
    let debounceTimer;
    return (...args) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => func.apply(this, args), delay);
    };
  };

  $("#select-plugin").on("click", () => $pluginSearch.focus());

  $("#plugin-search").on(
    "input",
    debounce((e) => {
      const inputValue = e.target.value.toLowerCase();
      let visibleItems = 0;

      pluginDropdownItems.each(function () {
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
        if ($pluginDropdownMenu.find(".no-items").length === 0) {
          $pluginDropdownMenu.append(
            '<li class="no-items dropdown-item text-muted">No Item</li>',
          );
        }
      } else {
        $pluginDropdownMenu.find(".no-items").remove();
      }
    }, 50),
  );

  // Clear search and "No Item" message when the dropdown is closed
  $("#select-plugin").on("hidden.bs.dropdown", () => {
    $("#plugin-search").val("").trigger("input");
    $(".no-items").remove();
  });

  // Attach event listener to handle mode changes when tabs are switched
  $('#service-modes-menu button[data-bs-toggle="tab"]').on(
    "shown.bs.tab",
    (e) => {
      handleModeChange($(e.target).data("bs-target"));
    },
  );

  $('#plugins-dropdown-menu button[data-bs-toggle="tab"]').on(
    "shown.bs.tab",
    (e) => {
      handleTabChange($(e.target).data("bs-target"));
    },
  );

  $(document).on("input", ".plugin-setting", function () {
    const isValid = $(this).data("pattern")
      ? new RegExp($(this).data("pattern")).test($(this).val())
      : true;
    $(this)
      .toggleClass("is-valid", isValid)
      .toggleClass("is-invalid", !isValid);
  });

  $(document).on("focusout", ".plugin-setting", function () {
    $(this).removeClass("is-valid");
  });

  $("#plugin-type-select").on("change", function () {
    currentType = $(this).val();
    const params =
      currentType === "all" ? { type: null } : { type: currentType };

    updateUrlParams(params);

    pluginDropdownItems.each(function () {
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

  $(document).on("click", ".show-multiple", function () {
    const toggleText = $(this).text().trim() === "SHOW" ? "HIDE" : "SHOW";
    $(this).html(
      `<i class="bx bx-${
        toggleText === "SHOW" ? "hide" : "show-alt"
      } bx-sm"></i>&nbsp;${toggleText}`,
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
          10,
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
    multipleClone.find(".show-multiple").before(`
      <div>
        <button id="remove-${cloneId}" type="button" class="btn btn-xs btn-text-danger rounded-pill remove-multiple p-0 pe-2">
          <i class="bx bx-trash bx-sm"></i>&nbsp;REMOVE
        </button>
      </div>
    `);

    // Insert the new element in the correct order based on suffix
    let inserted = false;
    existingContainers.each(function () {
      const containerSuffix = parseInt(
        $(this)
          .find(".multiple-collapse")
          .attr("id")
          .replace(`${multipleId}-`, ""),
        10,
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

    if (showMultiple.text().trim() === "SHOW") showMultiple.trigger("click");

    // Scroll to the newly added element smoothly
    multipleClone
      .focus()[0]
      .scrollIntoView({ behavior: "smooth", block: "start" });

    // Add the highlight class to the newly added clone with initial opacity
    multipleClone.addClass("multiple-highlight");

    // Use setTimeout to gradually fade out the highlight effect after the element is added
    setTimeout(() => {
      multipleClone.addClass("multiple-highlight-fade");
    }, 500); // Delay slightly increased to ensure the class is applied

    // Remove both classes after the transition completes
    setTimeout(() => {
      multipleClone.removeClass("multiple-highlight multiple-highlight-fade");
    }, 5000); // Adjusted to 5 seconds for a slower effect
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

  $("#save-settings").on("click", function () {
    const form = $("<form>", {
      method: "POST",
      action: window.location.href,
      class: "visually-hidden",
    });

    form.append(
      $("<input>", {
        type: "hidden",
        name: "csrf_token",
        value: $("#csrf_token").val(),
      }),
    );
    $("div[id^='navs-plugins-']")
      .find("input, select")
      .each(function () {
        const settingName = $(this).attr("name");
        const settingType = $(this).attr("type");
        const originalValue = $(this).data("original");
        var settingValue = $(this).val();

        if ($(this).is("select")) {
          settingValue = $(this).find("option:selected").val();
        } else if (settingType === "checkbox") {
          settingValue = $(this).prop("checked") ? "yes" : "no";
        }

        if (
          $(this).attr("id") &&
          !$(this).attr("id").startsWith("multiple-") &&
          settingValue == originalValue
        )
          return;

        form.append(
          $("<input>", {
            type: "hidden",
            name: settingName,
            value: settingValue,
          }),
        );
      });

    if (form.children().length < 2) {
      alert("No changes detected.");
      return;
    }
    form.appendTo("body").submit();
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
          .attr(
            "title",
            "Cannot remove because one or more settings are disabled",
          );

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

  var hasExternalPlugins = false;
  var hasProPlugins = false;
  pluginDropdownItems.each(function () {
    const type = $(this).data("type");
    if (type === "external") {
      hasExternalPlugins = true;
    } else if (type === "pro") {
      hasProPlugins = true;
    }
  });

  if (!hasExternalPlugins && !hasProPlugins) {
    $("#plugin-type-select").parent().remove();
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

  $("#plugin-type-select").trigger("change");
});
