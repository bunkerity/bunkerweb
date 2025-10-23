$(document).ready(function () {
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  let selectedService = $("#selected-service").val().trim();
  const originalService = selectedService;
  let selectedType = $("#selected-type").val().trim();
  const originalType = selectedType;
  const originalName = $("#config-name").val().trim();
  const editorElement = $("#config-value");
  const initialContent = editorElement.text().trim();
  const editor = ace.edit(editorElement[0]);
  const triggerConfigSave = () => {
    const $saveBtn = $(".save-config").not(".disabled");
    if ($saveBtn.length) {
      $saveBtn.first().trigger("click");
      return true;
    }
    return false;
  };

  var theme = $("#theme").val();

  function setEditorTheme() {
    if (theme === "dark") {
      editor.setTheme("ace/theme/cloud9_night");
    } else {
      editor.setTheme("ace/theme/cloud9_day");
    }
  }

  setEditorTheme();

  $("#dark-mode-toggle").on("change", function () {
    setTimeout(() => {
      theme = $("#theme").val();
      setEditorTheme();
    }, 30);
  });

  if (isReadOnly && window.location.pathname.endsWith("/new"))
    window.location.href = window.location.href.split("/new")[0];

  const language = editorElement.data("language"); // TODO: Support ModSecurity
  if (language === "NGINX") {
    editor.session.setMode("ace/mode/nginx");
  } else {
    editor.session.setMode("ace/mode/text"); // Default mode if language is unrecognized
  }

  const method = editorElement.data("method");
  const template = editorElement.data("template");
  if (method !== "ui" && template === "") {
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

  editor.commands.addCommand({
    name: "saveCustomConfigShortcut",
    bindKey: { win: "Ctrl-S", mac: "Command-S" },
    exec: () => {
      triggerConfigSave();
    },
    readOnly: false,
  });

  editorElement.removeClass("visually-hidden");
  $("#config-waiting").addClass("visually-hidden");

  const $serviceSearch = $("#service-search");
  const $serviceDropdownMenu = $("#services-dropdown-menu");
  const $serviceDropdownItems = $(
    "#services-dropdown-menu button.dropdown-item",
  );
  const $typeDropdownItems = $("#types-dropdown-menu li.nav-item");

  const changeTypesVisibility = () => {
    const isGlobal = selectedService.toLowerCase() === "global";
    $typeDropdownItems.each(function () {
      const item = $(this);
      item.toggle(isGlobal || item.data("context") === "multisite");
    });
  };

  $("#select-service").on("click", () => $serviceSearch.focus());

  $serviceSearch.on(
    "input",
    debounce((e) => {
      const inputValue = e.target.value.toLowerCase();
      let visibleItems = 0;

      $serviceDropdownItems.each(function () {
        const item = $(this);
        const matches = item.text().toLowerCase().includes(inputValue);

        item.parent().toggle(matches);

        if (matches) {
          visibleItems++; // Increment when an item is shown
        }
      });

      if (visibleItems === 0) {
        if ($serviceDropdownMenu.find(".no-service-items").length === 0) {
          $serviceDropdownMenu.append(
            '<li class="no-service-items dropdown-item text-muted" data-i18n="status.no_item">No Item</li>',
          );
        }
      } else {
        $serviceDropdownMenu.find(".no-service-items").remove();
      }
    }, 50),
  );

  $(document).on("hidden.bs.dropdown", "#select-service", function () {
    $("#service-search").val("").trigger("input");
  });

  $serviceDropdownItems.on("click", function () {
    const previousService = selectedService;
    selectedService = $(this).data("service");
    $("#service-display").text($(this).text().trim());
    changeTypesVisibility();
    if (
      selectedService.toLowerCase() === "global" &&
      previousService.toLowerCase() !== "global"
    ) {
      $("#select-type")
        .parent()
        .attr("data-bs-custom-class", "info-tooltip")
        .attr(
          "data-bs-original-title",
          "You can now select global types for your custom config.",
        )
        .tooltip("show");

      // Hide tooltip after 2 seconds
      setTimeout(() => {
        $("#select-type")
          .parent()
          .tooltip("hide")
          .attr("data-bs-original-title", "");
      }, 2000);
    } else if (
      selectedService.toLowerCase() !== "global" &&
      $(`#config-type-${selectedType}`).data("context") !== "multisite"
    ) {
      const firstMultisiteType = $(
        `#types-dropdown-menu li.nav-item[data-context="multisite"]`,
      ).first();
      const newTypeName = firstMultisiteType.text().trim();
      $("#select-type")
        .parent()
        .attr("data-bs-custom-class", "warning-tooltip")
        .attr(
          "data-bs-original-title",
          `Switched to ${newTypeName} as ${selectedType} is not a valid multisite type.`,
        )
        .tooltip("show");

      // Hide tooltip after 2 seconds
      setTimeout(() => {
        $("#select-type")
          .parent()
          .tooltip("hide")
          .attr("data-bs-original-title", "");
      }, 2000);

      firstMultisiteType.find("button").tab("show");
      selectedType = newTypeName;
      $("#type-display").text(newTypeName);
    }
  });

  $typeDropdownItems.on("click", function () {
    editor.session.setMode("ace/mode/nginx");
    selectedType = $(this).text().trim();
    $("#type-display").text(selectedType);
    // if (selectedType.startsWith("CRS") || selectedType.startsWith("MODSEC")) {
    //   editor.session.setMode("ace/mode/text"); // TODO: Support ModSecurity
    // } else {
    //   editor.session.setMode("ace/mode/nginx");
    // }
  });

  $(".save-config").on("click", function () {
    if (isReadOnly) {
      alert("This action is not allowed in read-only mode.");
      return;
    }
    const value = editor.getValue().trim();
    if (
      value &&
      value === initialContent &&
      selectedService === originalService &&
      selectedType === originalType &&
      $("#config-name").val().trim() === originalName
    ) {
      alert("No changes detected.");
      return;
    }

    const $configInput = $("#config-name");
    const configName = $configInput.val().trim();
    const pattern = $configInput.attr("pattern");
    let errorMessage = "";
    let isValid = true;

    if (!configName) {
      errorMessage = "A custom configuration name is required.";
      isValid = false;
    } else if (pattern && !new RegExp(pattern).test(configName))
      isValid = false;

    if (!isValid) {
      $configInput
        .attr(
          "data-bs-original-title",
          errorMessage || "Please enter a valid configuration name.",
        )
        .tooltip("show");

      // Hide tooltip after 2 seconds
      setTimeout(() => {
        $configInput.tooltip("hide").attr("data-bs-original-title", "");
      }, 2000);
      return;
    }

    const form = $("<form>", {
      method: "POST",
      action: window.location.href,
      class: "visually-hidden",
    });

    form.append(
      $("<input>", {
        type: "hidden",
        name: "service",
      }).val(selectedService),
    );
    form.append(
      $("<input>", {
        type: "hidden",
        name: "type",
      }).val(selectedType),
    );
    form.append(
      $("<input>", {
        type: "hidden",
        name: "name",
      }).val(configName),
    );
    form.append(
      $("<input>", {
        type: "hidden",
        name: "value",
      }).val(value),
    );
    form.append(
      $("<input>", {
        type: "hidden",
        name: "csrf_token",
      }).val($("#csrf_token").val()),
    );

    $(window).off("beforeunload");
    form.appendTo("body").submit();
  });

  changeTypesVisibility();

  $(document).on("keydown.configEditSave", function (e) {
    if (!(e.ctrlKey || e.metaKey)) return;
    if (e.key.toLowerCase() !== "s") return;
    if (!$(".save-config").length) return;

    if ($(e.target).hasClass("ace_text-input")) return;

    e.preventDefault();
    triggerConfigSave();
  });

  $(window).on("beforeunload", function (e) {
    if (isReadOnly) return;

    const value = editor.getValue().trim();
    if (
      value &&
      value === initialContent &&
      selectedService === originalService &&
      selectedType === originalType &&
      $("#config-name").val().trim() === originalName
    )
      return;

    // Cross-browser compatibility (for older browsers)
    var message =
      "Are you sure you want to leave? Changes you made may not be saved.";
    e.returnValue = message; // Standard for most browsers
    return message; // Required for some browsers
  });
});
