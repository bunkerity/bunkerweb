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

    const selected = new Set(
      value
        .split(/\s+/)
        .map((item) => item.trim())
        .filter(Boolean),
    );

    const dropdown = document.createElement("div");
    dropdown.className = "dropdown setting-multiselect";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className =
      "btn btn-outline-primary w-100 d-flex justify-content-between align-items-center setting-multiselect-toggle";
    toggle.dataset.bsToggle = "dropdown";
    toggle.dataset.bsAutoClose = "outside";

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

    toggle.append(toggleLabel, toggleBadge);

    const menu = document.createElement("div");
    menu.className = "dropdown-menu setting-multiselect-menu w-100 p-2";
    menu.addEventListener("click", (event) => event.stopPropagation());

    const refreshSummary = () => {
      const entries = [];
      menu.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
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
      this.setContent(
        toggleBadge,
        "template.editor.multiselect_summary",
        entries.length === 1 ? "{{count}} selected" : "{{count}} selected",
        { count: entries.length },
      );
    };

    options.forEach((option, index) => {
      const item = document.createElement("label");
      item.className = "dropdown-item d-flex align-items-start gap-2";
      item.setAttribute("role", "menuitemcheckbox");

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "form-check-input mt-0";
      checkbox.value = option.id;
      checkbox.dataset.label = option.label || option.id;
      checkbox.checked = selected.has(option.id);
      checkbox.id = `${this.settingId}-multiselect-${index}`;
      checkbox.addEventListener("change", refreshSummary);
      checkbox.addEventListener("click", (event) => event.stopPropagation());

      const label = document.createElement("span");
      label.className = "small flex-grow-1";
      label.textContent = option.label || option.id;

      item.append(checkbox, label);
      menu.append(item);
    });

    dropdown.append(toggle, menu);
    this.root.append(dropdown);
    this.primary = toggle;

    queueMicrotask(() => {
      if (typeof bootstrap !== "undefined" && bootstrap.Dropdown) {
        bootstrap.Dropdown.getOrCreateInstance(toggle);
      }
      refreshSummary();
    });

    this.valueGetter = () =>
      Array.from(menu.querySelectorAll('input[type="checkbox"]'))
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => checkbox.value)
        .join(" ");
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
