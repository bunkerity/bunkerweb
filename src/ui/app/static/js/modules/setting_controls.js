const controlRegistry = new WeakMap();

const normalizeDefaultValue = (entry, rawValue) => {
  if (typeof rawValue === "undefined" || rawValue === null || rawValue === "") {
    if (Object.prototype.hasOwnProperty.call(entry || {}, "default")) {
      const fallback = entry.default;
      if (typeof fallback === "string") return fallback;
      if (typeof fallback === "number" || typeof fallback === "boolean") {
        return String(fallback);
      }
    }
    return "";
  }
  return String(rawValue);
};

const parseMultivalueItems = (value, separator) => {
  if (!value) return [];
  if (separator) {
    return value
      .split(separator)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return value
    .split(/\s+/)
    .map((item) => item.trim())
    .filter(Boolean);
};

class SettingControl {
  constructor({ entry, value = "", settingId, translate }) {
    this.translate = translate || ((_, fallback) => fallback || "");
    this.settingId =
      settingId || `setting-${Math.random().toString(36).slice(2)}`;
    this.root = document.createElement("div");
    this.root.className = "setting-value-container d-flex flex-column gap-2";
    this.setEntry(entry, value);
    controlRegistry.set(this.root, this);
  }

  setContent(element, key, fallback, options) {
    if (!element) return;
    const text = this.translate(key, fallback, options);
    element.textContent = text;
    if (key) {
      element.setAttribute("data-i18n", key);
      if (options && Object.keys(options).length > 0) {
        element.setAttribute("data-i18n-options", JSON.stringify(options));
      } else {
        element.removeAttribute("data-i18n-options");
      }
    } else {
      element.removeAttribute("data-i18n");
      element.removeAttribute("data-i18n-options");
    }
  }

  setEntry(entry, value) {
    this.entry = entry || {};
    this.render(normalizeDefaultValue(this.entry, value));
  }

  render(value) {
    this.root.innerHTML = "";
    this.valueGetter = () => "";
    this.primary = null;

    const type = (this.entry?.type || "text").toLowerCase();

    switch (type) {
      case "check":
        this.renderCheck(value);
        break;
      case "select":
        this.renderSelect(value);
        break;
      case "multiselect":
        this.renderMultiselect(value);
        break;
      case "multivalue":
        this.renderMultivalue(value);
        break;
      case "number":
        this.renderText(value, "number");
        break;
      case "file":
        this.renderFile(value);
        break;
      case "password":
        this.renderPassword(value);
        break;
      default:
        this.renderText(value, "text");
        break;
    }
  }

  renderText(value, inputType) {
    const input = document.createElement("input");
    input.type = inputType;
    input.className = "form-control setting-value";
    input.dataset.settingType = inputType;
    if (inputType === "number") input.inputMode = "decimal";
    input.value = value;
    if (this.entry?.regex) input.setAttribute("pattern", this.entry.regex);
    this.root.append(input);
    this.primary = input;
    this.valueGetter = () => input.value.trim();
  }

  renderPassword(value) {
    const group = document.createElement("div");
    group.className = "input-group setting-password-group";

    const input = document.createElement("input");
    input.type = "password";
    input.className = "form-control setting-value";
    input.dataset.settingType = "password";
    input.autocomplete = "new-password";
    input.value = value;
    if (this.entry?.regex) input.setAttribute("pattern", this.entry.regex);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "btn btn-outline-secondary";
    toggle.innerHTML = '<i class="bx bx-show"></i>';
    toggle.addEventListener("click", () => {
      const isPassword = input.type === "password";
      input.type = isPassword ? "text" : "password";
      toggle.innerHTML = isPassword
        ? '<i class="bx bx-hide"></i>'
        : '<i class="bx bx-show"></i>';
      input.focus();
    });

    group.append(input, toggle);
    this.root.append(group);
    this.primary = input;
    this.valueGetter = () => input.value.trim();
  }

  renderCheck(value) {
    const isEnabled = /^(yes|true|1)$/i.test(value);

    const wrapper = document.createElement("div");
    wrapper.className = "form-check form-switch";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "form-check-input";
    const checkboxId = `${this.settingId}-switch`;
    checkbox.id = checkboxId;
    checkbox.checked = isEnabled;

    const label = document.createElement("label");
    label.className = "form-check-label text-muted small";
    label.setAttribute("for", checkboxId);
    this.setContent(label, "template.editor.setting_toggle_enabled", "Enabled");

    wrapper.append(checkbox, label);
    this.root.append(wrapper);
    this.primary = checkbox;
    this.valueGetter = () => (checkbox.checked ? "yes" : "no");
  }

  renderSelect(value) {
    const options = Array.isArray(this.entry?.options)
      ? this.entry.options
      : [];

    if (options.length === 0) {
      this.renderText(value, "text");
      return;
    }

    const select = document.createElement("select");
    select.className = "form-select setting-value";
    select.dataset.settingType = "select";

    options
      .map((option) => {
        if (
          typeof option === "string" ||
          typeof option === "number" ||
          typeof option === "boolean"
        ) {
          return { value: String(option), label: String(option) };
        }
        if (option && typeof option === "object") {
          const raw = option.value ?? option.id ?? option.label;
          if (typeof raw === "undefined") return null;
          return { value: String(raw), label: String(option.label ?? raw) };
        }
        return null;
      })
      .filter(Boolean)
      .forEach((option) => {
        const opt = document.createElement("option");
        opt.value = option.value;
        opt.textContent = option.label;
        select.append(opt);
      });

    const hasOption = Array.from(select.options).some(
      (opt) => opt.value === value,
    );
    if (hasOption) {
      select.value = value;
    } else if (select.options.length > 0) {
      select.value = select.options[0].value;
    }

    this.root.append(select);
    this.primary = select;
    this.valueGetter = () => select.value;
  }

  renderMultiselect(value) {
    const options = Array.isArray(this.entry?.multiselect)
      ? this.entry.multiselect.filter(
          (option) => option && typeof option === "object" && option.id,
        )
      : [];

    if (options.length === 0) {
      this.renderText(value, "text");
      return;
    }

    // Handle different separator types to split the value correctly
    let selectedArray;
    const separator = this.entry?.separator;

    if (separator === "") {
      // For empty separator, split the string into individual characters
      selectedArray = value.split("").filter(Boolean);
    } else if (separator !== undefined && separator !== null) {
      // For custom separator, split by that separator
      selectedArray = value
        .split(separator)
        .map((item) => item.trim())
        .filter(Boolean);
    } else {
      // For no separator defined, split by whitespace (default behavior)
      selectedArray = value
        .split(/\s+/)
        .map((item) => item.trim())
        .filter(Boolean);
    }

    const selected = new Set(selectedArray);

    const dropdown = document.createElement("div");
    dropdown.className = "dropdown setting-multiselect";
    dropdown.style.position = "relative";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className =
      "btn btn-outline-primary w-100 d-flex justify-content-between align-items-center setting-multiselect-toggle";
    toggle.dataset.bsToggle = "dropdown";
    toggle.dataset.bsAutoClose = "outside";

    const toggleContent = document.createElement("span");
    toggleContent.className =
      "d-flex justify-content-between align-items-center gap-2 flex-grow-1";

    const toggleLabel = document.createElement("span");
    toggleLabel.className = "flex-grow-1 text-truncate text-start";
    this.setContent(
      toggleLabel,
      "template.editor.multiselect_placeholder",
      "Select options",
    );

    const toggleBadge = document.createElement("span");
    toggleBadge.className = "badge bg-label-secondary ms-2";
    this.setContent(
      toggleBadge,
      "template.editor.multiselect_summary",
      "{{count}} selected",
      { count: selected.size },
    );

    toggleContent.append(toggleLabel, toggleBadge);
    toggle.append(toggleContent);

    const menu = document.createElement("div");
    menu.className = "dropdown-menu setting-multiselect-menu multiselect-menu";
    menu.addEventListener("click", (event) => event.stopPropagation());
    // Prevent Bootstrap Dropdown from capturing keyboard events (ArrowDown,
    // ArrowUp, Home, End, Escape) on any focused element inside the menu.
    // Without this, Bootstrap tries to call focus() on .dropdown-item elements
    // in a loop which can crash the browser tab.
    menu.addEventListener("keydown", (event) => event.stopPropagation());
    menu.addEventListener("keyup", (event) => event.stopPropagation());

    // Add search input
    const searchWrapper = document.createElement("div");
    searchWrapper.className =
      "p-2 border-bottom position-sticky top-0 multiselect-search-container";

    const searchRow = document.createElement("div");
    searchRow.className = "d-flex align-items-center gap-2";

    const searchGroup = document.createElement("div");
    searchGroup.className = "input-group input-group-sm flex-grow-1";

    const searchIcon = document.createElement("span");
    searchIcon.className = "input-group-text border-0 bg-transparent";
    searchIcon.innerHTML = '<i class="bx bx-search bx-sm"></i>';

    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.className = "form-control border-0 multiselect-search";
    searchInput.setAttribute("data-i18n", "form.placeholder.search");
    searchInput.placeholder = this.translate(
      "form.placeholder.search",
      "Search...",
    );
    searchInput.setAttribute(
      "aria-label",
      this.translate("form.placeholder.search", "Search..."),
    );
    searchInput.addEventListener("click", (e) => e.stopPropagation());
    // Prevent Bootstrap Dropdown from capturing keyboard events
    searchInput.addEventListener("keydown", (e) => e.stopPropagation());
    searchInput.addEventListener("keyup", (e) => e.stopPropagation());

    const selectedOnlyBtn = document.createElement("button");
    selectedOnlyBtn.type = "button";
    selectedOnlyBtn.className = "btn btn-sm multiselect-selected-only-btn";
    selectedOnlyBtn.setAttribute("data-bs-toggle", "tooltip");
    selectedOnlyBtn.setAttribute("data-bs-placement", "top");
    selectedOnlyBtn.setAttribute(
      "data-bs-original-title",
      this.translate("tooltip.button.show_selected_only", "Show selected only"),
    );
    selectedOnlyBtn.setAttribute(
      "data-i18n",
      "tooltip.button.show_selected_only",
    );
    selectedOnlyBtn.setAttribute("aria-pressed", "false");
    selectedOnlyBtn.innerHTML = '<i class="bx bx-check-double bx-xs"></i>';
    selectedOnlyBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isActive = selectedOnlyBtn.getAttribute("aria-pressed") === "true";
      selectedOnlyBtn.setAttribute("aria-pressed", String(!isActive));
      selectedOnlyBtn.classList.toggle("active", !isActive);
      applyFilters();
    });

    searchGroup.append(searchIcon, searchInput);
    searchRow.append(searchGroup, selectedOnlyBtn);
    searchWrapper.append(searchRow);
    // Only show search bar when there are more than 10 options
    if (options.length <= 10) {
      searchWrapper.classList.add("d-none");
    }
    menu.append(searchWrapper);

    // Options container
    const optionsContainer = document.createElement("div");
    optionsContainer.className =
      "setting-multiselect-options multiselect-options";

    // Pre-create "no items found" message (hidden by default)
    const noOptionsMsg = document.createElement("div");
    noOptionsMsg.className =
      "dropdown-item no-options-message border-0 p-3 text-center small d-none";
    const noOptionsMsgSpan = document.createElement("span");
    this.setContent(
      noOptionsMsgSpan,
      "status.no_search_results",
      "No items found.",
    );
    noOptionsMsg.append(noOptionsMsgSpan);

    // Pre-declare footerText so refreshSummary can update it once assigned
    let footerText = null;

    const refreshSummary = () => {
      const entries = [];
      Array.from(
        optionsContainer.querySelectorAll('input[type="checkbox"]'),
      ).forEach((checkbox) => {
        if (checkbox.checked) {
          entries.push({
            id: checkbox.value,
            label: checkbox.dataset.label || checkbox.value,
          });
        }
      });
      if (entries.length === 0) {
        this.setContent(
          toggleLabel,
          "template.editor.multiselect_placeholder",
          "Select options",
        );
      } else {
        toggleLabel.textContent = entries
          .map((entry) => entry.label)
          .join(", ");
        toggleLabel.removeAttribute("data-i18n");
        toggleLabel.removeAttribute("data-i18n-options");
      }
      toggleBadge.textContent = entries.length;
      if (footerText) {
        this.setContent(
          footerText,
          "template.editor.multiselect_summary",
          "{{count}} selected",
          { count: entries.length },
        );
      }
    };

    const applyFilters = () => {
      const lowerTerm = searchInput.value.toLowerCase().trim();
      const selectedOnly =
        selectedOnlyBtn.getAttribute("aria-pressed") === "true";
      let visibleCount = 0;

      // Use d-none toggling; items have d-flex which overrides inline display:none
      optionsContainer.querySelectorAll("label").forEach((item) => {
        const text = item.textContent.toLowerCase();
        const isChecked = item.querySelector('input[type="checkbox"]')?.checked;
        const matchesSearch = !lowerTerm || text.includes(lowerTerm);
        const matchesFilter = !selectedOnly || isChecked;

        if (matchesSearch && matchesFilter) {
          item.classList.remove("d-none");
          visibleCount++;
        } else {
          item.classList.add("d-none");
        }
      });

      if (visibleCount === 0) {
        noOptionsMsg.classList.remove("d-none");
      } else {
        noOptionsMsg.classList.add("d-none");
      }
    };

    searchInput.addEventListener("input", () => applyFilters());

    options.forEach((option, index) => {
      const item = document.createElement("label");
      item.className =
        "dropdown-item d-flex align-items-center gap-2 py-2 px-3 cursor-pointer multiselect-option";
      item.setAttribute("role", "menuitemcheckbox");
      item.setAttribute("data-option-id", option.id);
      item.setAttribute("for", `${this.settingId}-multiselect-${index}`);
      item.title = option.label || option.id;

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "form-check-input m-0";
      checkbox.value = option.id;
      checkbox.dataset.label = option.label || option.id;
      checkbox.checked = selected.has(option.id);
      checkbox.id = `${this.settingId}-multiselect-${index}`;
      checkbox.addEventListener("change", () => {
        refreshSummary();
        applyFilters();
      });

      const labelSpan = document.createElement("span");
      labelSpan.className = "flex-grow-1 small";
      labelSpan.textContent = option.label || option.id;

      item.append(checkbox, labelSpan);
      optionsContainer.append(item);
    });

    optionsContainer.append(noOptionsMsg);
    menu.append(optionsContainer);

    // Add footer with count
    const footer = document.createElement("div");
    footer.className = "p-2 border-top text-center";
    footerText = document.createElement("small");
    footerText.className = "text-muted";
    this.setContent(
      footerText,
      "template.editor.multiselect_summary",
      "{{count}} selected",
      { count: 0 },
    );
    footer.append(footerText);
    menu.append(footer);

    dropdown.append(toggle, menu);
    this.root.append(dropdown);
    this.primary = toggle;

    queueMicrotask(() => {
      if (typeof bootstrap !== "undefined" && bootstrap.Dropdown) {
        bootstrap.Dropdown.getOrCreateInstance(toggle);
      }
      if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
        // Use a dynamic title function so applyTranslations() updates to
        // data-bs-original-title are picked up on every show
        // (Bootstrap 5 Tooltip lacks setContent unlike Popover).
        new bootstrap.Tooltip(selectedOnlyBtn, {
          title() {
            return selectedOnlyBtn.getAttribute("data-bs-original-title");
          },
        });
      }
      refreshSummary();
    });

    this.valueGetter = () => {
      const separator = this.entry?.separator;
      const joinSeparator =
        separator !== undefined && separator !== null ? separator : " ";
      return Array.from(
        optionsContainer.querySelectorAll('input[type="checkbox"]'),
      )
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => checkbox.value)
        .join(joinSeparator);
    };
  }

  renderMultivalue(value) {
    const separator = this.entry?.separator || " ";
    const values = parseMultivalueItems(value, this.entry?.separator);

    const list = document.createElement("div");
    list.className = "setting-multivalue-list d-flex flex-column gap-2";

    const helper = document.createElement("small");
    helper.className = "text-muted";
    const helperOptions = {
      separatorNote: separator ? ` Will be joined with "${separator}".` : "",
    };
    this.setContent(
      helper,
      "template.editor.multivalue_helper",
      "One value per line.{{separatorNote}}",
      helperOptions,
    );

    const addButton = document.createElement("button");
    addButton.type = "button";
    addButton.className = "btn btn-outline-primary btn-sm align-self-start";
    const addIcon = document.createElement("i");
    addIcon.className = "bx bx-plus";
    const addText = document.createElement("span");
    addText.className = "ms-1";
    this.setContent(addText, "template.editor.multivalue_add", "Add value");
    addButton.append(addIcon, addText);

    const createRow = (initial = "") => {
      const row = document.createElement("div");
      row.className = "input-group input-group-sm setting-multivalue-row";

      const input = document.createElement("input");
      input.type = "text";
      input.className = "form-control setting-multivalue-input";
      if (this.entry?.regex) input.setAttribute("pattern", this.entry.regex);
      input.value = initial;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "btn btn-outline-danger";
      removeBtn.innerHTML = '<i class="bx bx-x"></i>';
      removeBtn.addEventListener("click", () => {
        if (list.children.length === 1) {
          input.value = "";
          return;
        }
        row.remove();
      });

      row.append(input, removeBtn);
      return { row, input };
    };

    if (values.length === 0) {
      const { row } = createRow("");
      list.append(row);
    } else {
      values.forEach((item) => {
        const { row } = createRow(item);
        list.append(row);
      });
    }

    addButton.addEventListener("click", () => {
      const { row, input } = createRow("");
      list.append(row);
      input.focus();
    });

    this.root.append(list, addButton, helper);
    this.primary = list.querySelector("input");
    this.valueGetter = () =>
      Array.from(list.querySelectorAll(".setting-multivalue-input"))
        .map((input) => input.value.trim())
        .filter(Boolean)
        .join(separator || " ");
  }

  renderMultiselectMenu() {
    // placeholder handled in renderMultiselect
  }

  renderFile(value) {
    const wrapper = document.createElement("div");
    wrapper.className = "setting-file-wrapper d-flex flex-column gap-2";

    const hidden = document.createElement("textarea");
    hidden.className = "d-none setting-value";
    hidden.dataset.settingType = "file";
    hidden.value = value;
    if (this.entry?.regex) hidden.setAttribute("pattern", this.entry.regex);

    const upload = document.createElement("input");
    upload.type = "file";
    upload.className = "form-control";
    if (typeof this.entry?.accept === "string" && this.entry.accept.trim()) {
      upload.setAttribute("accept", this.entry.accept.trim());
    }

    const status = document.createElement("small");
    status.className = "text-muted";
    status.textContent = value
      ? `Current content loaded (${value.length} chars)`
      : "No file selected";

    upload.addEventListener("change", () => {
      const file = upload.files && upload.files[0];
      if (!file) {
        status.textContent = hidden.value
          ? `Current content loaded (${hidden.value.length} chars)`
          : "No file selected";
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const content = String(event.target?.result ?? "")
          .replace(/\r\n/g, "\n")
          .replace(/\r/g, "\n");
        hidden.value = content;
        status.textContent = `Loaded: ${file.name} (${content.length} chars)`;
      };
      reader.onerror = () => {
        status.textContent = `Unable to read: ${file.name}`;
        // Clear on failure so selecting the same file retriggers change.
        upload.value = "";
      };
      reader.readAsText(file);
    });

    wrapper.append(upload, hidden, status);
    this.root.append(wrapper);
    this.primary = upload;
    this.valueGetter = () => hidden.value.trim();
  }

  focus() {
    if (this.primary && typeof this.primary.focus === "function") {
      this.primary.focus();
    }
  }

  getValue() {
    return this.valueGetter ? this.valueGetter() : "";
  }

  getPrimaryInput() {
    return this.primary || null;
  }
}

export const createSettingControl = (options) => new SettingControl(options);

export const updateSettingControl = (control, { entry, value }) => {
  if (!control) return;
  control.setEntry(entry, value);
};

export const getSettingControlValue = (control) =>
  control ? control.getValue() : "";

export const getSettingControlPrimary = (control) =>
  control ? control.getPrimaryInput() : null;

export const getControlFromElement = (element) => controlRegistry.get(element);
