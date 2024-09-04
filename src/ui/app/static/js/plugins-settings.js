$(document).ready(() => {
  let currentPlugin = "general";
  let currentMode = "easy";
  let currentType = "all";
  let currentKeywords = "";
  const pluginDropdownItems = $("#plugins-dropdown-menu li.nav-item");

  const updateUrlParams = (params) => {
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

    // Push the updated URL (this keeps the hash and the merged search params)
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
      updateUrlParams(params);
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

  $(".show-multiple").on("click", function () {
    const toggleText = $(this).text().trim() === "SHOW" ? "HIDE" : "SHOW";
    $(this).html(
      `<i class="bx bx-${
        toggleText === "SHOW" ? "hide" : "show-alt"
      } bx-sm"></i>&nbsp;${toggleText}`,
    );
  });

  $(".add-multiple").on("click", function () {
    const showButtonId = $(this).attr("id").replace("add", "show");
    if ($(`#${showButtonId}`).text().trim() === "SHOW") {
      $(`#${showButtonId}`).trigger("click");
    }
  });

  $('div[id^="multiple-"]')
    .filter(function () {
      return !/^multiple-.*-\d+$/.test($(this).attr("id"));
    })
    .each(function () {
      let defaultValues = true;
      $(this)
        .find("input, select")
        .each(function () {
          const type = $(this).attr("type");
          const defaultVal = $(this).data("default");
          const isChecked =
            type === "checkbox" &&
            $(this).prop("checked") === (defaultVal === "yes");
          const isMatchingValue =
            type !== "checkbox" && $(this).val() === defaultVal;

          if (!isChecked && !isMatchingValue) defaultValues = false;
        });

      if (defaultValues) $(`#show-${$(this).attr("id")}`).trigger("click");
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

  const hash = window.location.hash;
  if (hash) {
    const targetTab = $(
      `button[data-bs-target="#navs-plugins-${hash.substring(1)}"]`,
    );
    if (targetTab.length) targetTab.tab("show");
  }

  $("#plugin-type-select").trigger("change");
});
