$(document).ready(() => {
  let currentPlugin = "general";
  let currentMode = "easy";
  let currentType = "all";
  let currentKeywords = "";
  const pluginDropdownItems = $("#plugins-dropdown-menu li.nav-item");

  const updateUrlParams = (params, removeHash = false) => {
    // Create a new URL based on the current location (this keeps both the search params and the hash)
    const newUrl = new URL(window.location.href);

    // Merge existing search parameters with new parameters
    const searchParams = new URLSearchParams(newUrl.search);

    // Add or update the parameters with the new values passed in the `params` object
    Object.keys(params).forEach((key) => {
      searchParams.set(key, params[key]);
    });

    // Update the search params of the URL
    newUrl.search = searchParams.toString();

    // Optionally remove the hash from the URL
    if (removeHash) {
      newUrl.hash = "";
    }

    // Push the updated URL (this keeps or removes the hash and updates the search params)
    history.pushState(params, document.title, newUrl.toString());
  };

  $("#select-plugin").on("click", () => $("#plugin-search").focus());

  // Debounce for search input to avoid triggering the search on every keystroke
  let debounceTimer;
  $("#plugin-search").on("input", (e) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const inputValue = e.target.value.toLowerCase();

      pluginDropdownItems.each(function () {
        const item = $(this);
        if (currentType !== "all" && item.data("type") !== currentType) return;

        const text = item.text().toLowerCase();
        const pluginId = item
          .find("button")
          .data("bs-target")
          .replace("#navs-plugins-", "");

        text.includes(inputValue) || pluginId.includes(inputValue)
          ? item.show()
          : item.hide();
      });

      // Show "No Item" message if no items match
      const noVisibleItems =
        pluginDropdownItems.filter(":visible").length === 0;
      if (noVisibleItems && $(".no-items").length === 0) {
        $("#plugins-dropdown-menu").append(
          '<li class="no-items dropdown-item text-muted">No Item</li>',
        );
      } else {
        $(".no-items").remove();
      }
    }, 300); // 300ms delay for debounce
  });

  $("#select-plugin").on("hidden.bs.dropdown", () => {
    $("#plugin-search").val("").trigger("input");
    $(".no-items").remove();
  });

  const handleModeChange = (targetClass) => {
    currentMode = targetClass.substring(1).replace("navs-modes-", "");
    if (currentMode === "easy") {
      updateUrlParams(currentType !== "all" ? { type: currentType } : {});
    } else {
      updateUrlParams({ mode: currentMode });
    }
  };

  $('#service-modes-menu button[data-bs-toggle="tab"]').on(
    "shown.bs.tab",
    (e) => {
      handleModeChange($(e.target).data("bs-target"));
    },
  );

  const handleTabChange = (targetClass) => {
    currentPlugin = targetClass.substring(1).replace("navs-plugins-", "");
    if (currentPlugin === "general" && window.location.hash) {
      const params = {};
      if (currentType !== "all") params.type = currentType;
      if (currentMode !== "easy") params.mode = currentMode;
      // Call updateUrlParams with `removeHash = true` to remove the hash
      updateUrlParams(params, true);
    } else {
      window.location.hash = currentPlugin;
    }
  };

  $('#plugins-dropdown-menu button[data-bs-toggle="tab"]').on(
    "shown.bs.tab",
    (e) => {
      handleTabChange($(e.target).data("bs-target"));
    },
  );

  $(".plugin-setting").on("input", function () {
    const isValid = $(this).data("pattern")
      ? new RegExp($(this).data("pattern")).test($(this).val())
      : true;
    $(this)
      .toggleClass("is-valid", isValid)
      .toggleClass("is-invalid", !isValid);
  });

  $(".plugin-setting").on("focusout", function () {
    $(this).removeClass("is-valid");
  });

  $("#plugin-type-select").on("change", function () {
    currentType = $(this).val();
    const params = currentType === "all" ? {} : { type: currentType };

    updateUrlParams(params);

    pluginDropdownItems.each(function () {
      $(this).toggle(
        currentType === "all" || $(this).data("type") === currentType,
      );
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
    const suffix = $(`#${multipleId}`).find(".multiple-container").length;
    const cloneId = `${multipleId}-${suffix}`;

    // Clone the first .multiple-container and reset input values
    const multipleClone = $(`#${multipleId}`)
      .find(".multiple-container")
      .first()
      .clone();

    // Update the IDs and names of the cloned inputs/selects
    multipleClone.find("input, select").each(function () {
      const type = $(this).attr("type");
      const defaultVal = $(this).data("default");

      // Enable the inputs/selects and update values
      $(this).attr("disabled", false);
      const newId = $(this).attr("id").replace("-0", `-${suffix}`);
      const newName = `${$(this).attr("name")}_${suffix}`;
      $(this).attr("id", newId).attr("name", newName);

      // Update the label for the input/select
      const settingLabel = $(this).next("label");
      settingLabel.attr("for", newId).text(`${settingLabel.text()}_${suffix}`);

      // Update value to an empty string or default value
      if ($(this).is("select")) {
        $(this).val(defaultVal);
        $(this)
          .find("option")
          .each(function () {
            $(this).prop("selected", false);
          });
      } else if (type === "checkbox") {
        $(this).prop("checked", false);
      } else {
        $(this).val("");
      }
    });

    // Update the collapse section's ID and remove tooltips
    multipleClone
      .find(".multiple-collapse")
      .attr("id", `${cloneId}`)
      .find('[data-bs-toggle="tooltip"]:not(.badge)')
      .each(function () {
        $(this)
          .removeAttr("data-bs-toggle")
          .removeAttr("data-bs-placement")
          .removeAttr("data-bs-original-title");
      });

    // Add the #suffix to h6
    const multipleTitle = multipleClone.find("h6");
    multipleTitle.text(`${multipleTitle.text()} #${suffix}`);

    // Append the "REMOVE" button
    multipleClone.find(".add-multiple").remove();
    multipleClone.find(".show-multiple").before(
      `<div>
  <button id="remove-${cloneId}"
          type="button"
          class="btn btn-xs btn-text-danger rounded-pill remove-multiple p-0 pe-2">
      <i class="bx bx-trash bx-sm"></i>&nbsp;REMOVE
  </button>
</div>`,
    );

    // Append the cloned element to the container
    $(`#${multipleId}`).append(multipleClone);

    // Reinitialize Bootstrap tooltips for the newly added clone
    multipleClone.find('[data-bs-toggle="tooltip"]').tooltip();

    // Update the data-bs-target and aria-controls attributes of the show-multiple button
    const showMultiple = multipleClone.find(".show-multiple");
    showMultiple
      .attr("data-bs-target", `#${cloneId}`)
      .attr("aria-controls", cloneId);
    if (showMultiple.text().trim() === "SHOW") showMultiple.trigger("click");

    // Scroll to the newly added element
    multipleClone.focus()[0].scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
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

    // Update all next elements' IDs and names
    elementToRemove.nextAll().each(function () {
      const nextId = $(this).find(".multiple-collapse").attr("id");
      const nextSuffix = parseInt(
        nextId.substring(nextId.lastIndexOf("-") + 1),
        10,
      );
      const newSuffix = nextSuffix - 1;
      const newId = nextId.replace(`-${nextSuffix}`, `-${newSuffix}`);

      // Update the ID of the next element
      $(this).find(".multiple-collapse").attr("id", newId);

      const multipleTitle = $(this).find("h6");
      multipleTitle.text(function () {
        return $(this).text().replace(` #${nextSuffix}`, ` #${newSuffix}`);
      });

      // Update the input/select name and corresponding label
      $(this)
        .find("input, select")
        .each(function () {
          const newName = $(this)
            .attr("name")
            .replace(`_${nextSuffix}`, `_${newSuffix}`);
          $(this).attr("name", newName);

          // Find the associated label and update its 'for' attribute and text
          const settingLabel = $(`label[for="${$(this).attr("id")}"]`);
          if (settingLabel.length) {
            settingLabel.attr("for", newId).text(function () {
              return $(this).text().replace(`_${nextSuffix}`, `_${newSuffix}`);
            });
          }
        });

      // Update the data-bs-target and aria-controls of the show-multiple button
      const showMultiple = $(this).find(".show-multiple");
      showMultiple
        .attr("data-bs-target", `#${newId}`)
        .attr("aria-controls", newId);

      const removeMultiple = $(this).find(".remove-multiple");
      removeMultiple.attr("id", `remove-${newId}`);
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
