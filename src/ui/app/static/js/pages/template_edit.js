import {
  createSettingControl,
  getSettingControlPrimary,
  getSettingControlValue,
  updateSettingControl,
} from "../modules/setting_controls.js";

const ctx = window.templateEditorContext || {};

const runTranslations = () => {
  if (
    typeof window !== "undefined" &&
    typeof window.applyTranslations === "function"
  ) {
    window.applyTranslations();
  } else if (typeof applyTranslations === "function") {
    applyTranslations();
  }
};

const translate = (key, fallback, options) => {
  if (typeof i18next !== "undefined" && typeof i18next.t === "function") {
    return i18next.t(key, {
      defaultValue: fallback || key,
      ...(options || {}),
    });
  }
  if (fallback) return fallback;
  return key;
};

const dom = {
  form: document.getElementById("template-form"),
  fieldset: document.getElementById("template-form-fieldset"),
  feedback: document.getElementById("template-form-feedback"),
  settingsList: document.getElementById("settings-list"),
  settingsEmpty: document.getElementById("settings-empty"),
  settingSelectorOpenBtn: document.getElementById("open-setting-selector"),
  settingSelectorModal: document.getElementById("setting-selector-modal"),
  settingRemoveModal: document.getElementById("setting-remove-modal"),
  settingRemoveName: document.getElementById("setting-remove-name"),
  confirmSettingRemoveBtn: document.getElementById("confirm-setting-remove"),
  settingSelectorSearch: document.getElementById("setting-selector-search"),
  settingSelectorClear: document.getElementById("setting-selector-clear"),
  settingSelectorPlugin: document.getElementById("setting-selector-plugin"),
  settingSelectorType: document.getElementById("setting-selector-type"),
  settingSelectorResults: document.getElementById("setting-selector-results"),
  settingSelectorEmpty: document.getElementById("setting-selector-empty"),
  settingSelectorCount: document.getElementById("setting-selector-count"),
  settingSelectorApply: document.getElementById("setting-selector-apply"),
  stepsList: document.getElementById("steps-list"),
  stepsEmpty: document.getElementById("steps-empty"),
  addStepBtn: document.getElementById("add-step-btn"),
  configsList: document.getElementById("configs-list"),
  configsEmpty: document.getElementById("configs-empty"),
  addConfigBtn: document.getElementById("add-config-btn"),
  templateIdInput: document.getElementById("template-id"),
  templateNameInput: document.getElementById("template-name"),
  saveButton: document.getElementById("save-template-btn"),
  // Delete step confirmation modal elements
  deleteStepModal: document.getElementById("modal-delete-step"),
  deleteStepTitle: document.getElementById("delete-step-title"),
  deleteStepItems: document.getElementById("delete-step-items"),
  confirmDeleteStepBtn: document.getElementById("confirm-delete-step-btn"),
};

const normalizeSettingKey = (value) =>
  typeof value === "string" ? value.trim().toUpperCase() : "";

const rawSettingsCatalog = Array.isArray(ctx.multisiteSettingsCatalog)
  ? ctx.multisiteSettingsCatalog
  : [];

const pluginTypeLabels = {
  general: translate("plugin.type.core", "Core"),
  core: translate("plugin.type.core", "Core"),
  pro: translate("plugin.type.pro", "Pro"),
  external: translate("plugin.type.external", "External"),
  ui: translate("plugin.type.external", "External"),
};

const normalizeCatalogEntry = (entry, index) => {
  if (!entry || typeof entry !== "object") return null;
  const key = typeof entry.key === "string" ? entry.key.trim() : "";
  if (!key) return null;

  const plugin =
    entry.plugin && typeof entry.plugin === "object" ? entry.plugin : {};
  const pluginId =
    typeof plugin.id === "string" && plugin.id.trim()
      ? plugin.id.trim()
      : "general";
  const pluginName =
    typeof plugin.name === "string" && plugin.name.trim()
      ? plugin.name.trim()
      : pluginId;
  const pluginTypeRaw =
    typeof plugin.type === "string" && plugin.type.trim()
      ? plugin.type.trim().toLowerCase()
      : pluginId === "general"
        ? "general"
        : "core";
  const pluginCategory =
    typeof plugin.category === "string" ? plugin.category.trim() : "";

  const label =
    typeof entry.label === "string" && entry.label.trim()
      ? entry.label.trim()
      : key;
  const description =
    typeof entry.description === "string" ? entry.description.trim() : "";
  const type = typeof entry.type === "string" ? entry.type.trim() : "";

  let defaultValue = "";
  if (Object.prototype.hasOwnProperty.call(entry, "default")) {
    const rawDefault = entry.default;
    if (
      rawDefault !== null &&
      typeof rawDefault === "object" &&
      typeof rawDefault.toJSON !== "function"
    ) {
      defaultValue = JSON.stringify(rawDefault);
    } else if (rawDefault === null || typeof rawDefault === "undefined") {
      defaultValue = "";
    } else {
      defaultValue = String(rawDefault);
    }
  }

  const tags = Array.isArray(entry.tags)
    ? entry.tags
        .map((tag) =>
          typeof tag === "string" || typeof tag === "number" ? String(tag) : "",
        )
        .filter(Boolean)
    : [];

  const keyUpper = key.toUpperCase();
  const keyLower = keyUpper.toLowerCase();
  const labelLower = label.toLowerCase();
  const pluginNameLower = pluginName.toLowerCase();
  const pluginCategoryLower = pluginCategory.toLowerCase();
  const descriptionLower = description.toLowerCase();
  const typeLower = type.toLowerCase();

  const tagTokens = tags.map((tag) => tag.toLowerCase());

  const pluginOrder = Number.isFinite(entry.plugin_order)
    ? Number(entry.plugin_order)
    : 100000;
  const settingOrder = Number.isFinite(entry.setting_order)
    ? Number(entry.setting_order)
    : 100000;

  const tokenSet = new Set([
    keyLower,
    labelLower,
    pluginNameLower,
    pluginTypeRaw,
    pluginCategoryLower,
    ...tagTokens,
  ]);
  labelLower.split(/\s+/).forEach((token) => {
    if (token) tokenSet.add(token);
  });
  pluginNameLower.split(/\s+/).forEach((token) => {
    if (token) tokenSet.add(token);
  });

  const popularity = Math.max(
    0,
    200000 - pluginOrder * 1000 - settingOrder * 10 - index,
  );

  return {
    key,
    keyUpper,
    keyLower,
    label,
    labelLower,
    description,
    descriptionLower,
    type,
    typeLower,
    defaultValue,
    default: entry.default,
    pluginId,
    pluginName,
    pluginNameLower,
    pluginType: pluginTypeRaw,
    pluginCategory,
    pluginCategoryLower,
    tags,
    tagTokens,
    pluginOrder,
    settingOrder,
    options: Array.isArray(entry.options) ? entry.options : [],
    multiselect: Array.isArray(entry.multiselect) ? entry.multiselect : [],
    separator: typeof entry.separator === "string" ? entry.separator : "",
    docs:
      typeof entry.docs === "string"
        ? entry.docs.trim()
        : typeof plugin.docs === "string"
          ? plugin.docs.trim()
          : "",
    multiple: Boolean(entry.multiple),
    regex: typeof entry.regex === "string" ? entry.regex : "",
    advanced: Boolean(entry.advanced),
    tokens: Array.from(tokenSet),
    popularity,
  };
};

const settingsCatalog = rawSettingsCatalog
  .map(normalizeCatalogEntry)
  .filter(Boolean);

settingsCatalog.sort((a, b) => {
  if (a.pluginOrder !== b.pluginOrder) {
    return a.pluginOrder - b.pluginOrder;
  }
  if (a.settingOrder !== b.settingOrder) {
    return a.settingOrder - b.settingOrder;
  }
  return a.labelLower.localeCompare(b.labelLower, undefined, {
    sensitivity: "base",
  });
});

const catalogByKey = new Map();
settingsCatalog.forEach((entry) => {
  if (!catalogByKey.has(entry.keyUpper)) {
    catalogByKey.set(entry.keyUpper, entry);
  }
});

const getCatalogEntry = (key) => catalogByKey.get(normalizeSettingKey(key));

const pluginOptionMap = new Map();
settingsCatalog.forEach((entry) => {
  const existing = pluginOptionMap.get(entry.pluginId);
  if (!existing || entry.pluginOrder < existing.order) {
    pluginOptionMap.set(entry.pluginId, {
      id: entry.pluginId,
      name: entry.pluginName,
      type: entry.pluginType,
      order: entry.pluginOrder,
    });
  }
});

const typeOptions = Array.from(
  new Set(settingsCatalog.map((entry) => entry.type).filter(Boolean)),
).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));

const settingSelectorState = {
  query: "",
  plugin: "",
  type: "",
  entries: [],
  selectedKey: null,
  modalOpen: false,
};

let settingSelectorModalInstance = null;
const ensureSettingRemoveModal = () => {
  if (settingRemoveModalInstance || !dom.settingRemoveModal) return;
  if (typeof bootstrap === "undefined" || !bootstrap.Modal) return;
  settingRemoveModalInstance = bootstrap.Modal.getOrCreateInstance(
    dom.settingRemoveModal,
    {},
  );
};

const closeSettingRemoveModal = () => {
  if (!dom.settingRemoveModal) return;
  ensureSettingRemoveModal();
  settingRemoveModalInstance?.hide();
};

const counters = {
  settings: document.getElementById("summary-settings-count"),
  steps: document.getElementById("summary-steps-count"),
  configs: document.getElementById("summary-configs-count"),
};

const state = {
  settingCounter: 0,
  configCounter: 0,
  stepCounter: 0,
  isSaving: false,
  stepToDelete: null,
  settingToRemove: null,
};

let deleteStepModalInstance = null;
let settingRemoveModalInstance = null;

const buildDeleteStepModalHTML = () => {
  const title = translate("modal.title.delete_step", "Delete step");
  const confirmText = translate("button.delete", "Delete");
  const cancelText = translate("button.cancel", "Cancel");
  const alertText = translate(
    "modal.body.delete_step_confirmation",
    "Are you sure you want to delete this step?",
  );
  const nameLabel = translate("modal.body.delete_step_name_label", "Step");
  const contentLabel = translate(
    "modal.body.delete_step_content_label",
    "Content",
  );

  return `
  <div class="modal fade" id="modal-delete-step" tabindex="-1" aria-labelledby="modal-delete-step-label" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
      <div class="modal-content border-0 shadow-sm rounded-3">
        <div class="modal-header border-0 pb-0">
          <h5 class="modal-title d-flex align-items-center gap-2" id="modal-delete-step-label">
            <i class="bx bx-trash text-danger"></i>
            <span data-i18n="modal.title.delete_step">${title}</span>
          </h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="${translate(
            "button.close",
            "Close",
          )}" data-i18n-aria-label="button.close"></button>
        </div>
        <div class="modal-body pt-2">
          <div class="alert alert-warning d-flex align-items-start gap-2 mb-3" role="alert">
            <i class="bx bx-error-circle bx-sm flex-shrink-0"></i>
            <div data-i18n="modal.body.delete_step_confirmation">${alertText}</div>
          </div>
          <ul class="list-group list-group-flush border rounded-3 shadow-sm overflow-hidden">
            <li class="list-group-item d-flex justify-content-between align-items-center">
              <span class="d-flex align-items-center gap-2 text-muted">
                <i class="bx bx-spreadsheet"></i>
                <span data-i18n="modal.body.delete_step_name_label">${nameLabel}</span>
              </span>
              <span id="delete-step-title" class="fw-semibold text-truncate" style="max-width: 60%"></span>
            </li>
            <li class="list-group-item d-flex justify-content-between align-items-center">
              <span class="d-flex align-items-center gap-2 text-muted">
                <i class="bx bx-list-ul"></i>
                <span data-i18n="modal.body.delete_step_content_label">${contentLabel}</span>
              </span>
              <span id="delete-step-items" class="fw-semibold"></span>
            </li>
          </ul>
        </div>
        <div class="modal-footer border-0">
          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal"><span data-i18n="button.cancel">${cancelText}</span></button>
          <button type="button" class="btn btn-danger ms-1" id="confirm-delete-step-btn">
            <i class="bx bx-trash"></i>
            <span data-i18n="button.delete">${confirmText}</span>
          </button>
        </div>
      </div>
    </div>
  </div>`;
};

const bindDeleteStepModalEvents = () => {
  if (!dom.deleteStepModal) return;
  // Confirm deletion
  if (dom.confirmDeleteStepBtn) {
    dom.confirmDeleteStepBtn.addEventListener("click", () => {
      if (!state.stepToDelete) return;
      const wrapper = state.stepToDelete;
      getStepSettings(wrapper).forEach((key) => settingAssignments.delete(key));
      getStepConfigs(wrapper).forEach((ref) => configAssignments.delete(ref));
      wrapper.remove();
      state.stepToDelete = null;
      refreshStepOptions();
      reindexSteps();
      updateSummary();
      if (deleteStepModalInstance) deleteStepModalInstance.hide();
    });
  }

  // Cleanup on modal hide
  dom.deleteStepModal.addEventListener("hidden.bs.modal", () => {
    state.stepToDelete = null;
    if (dom.deleteStepTitle) dom.deleteStepTitle.textContent = "";
    if (dom.deleteStepItems) dom.deleteStepItems.textContent = "";
  });
};

const createDeleteStepModalIfNeeded = () => {
  if (dom.deleteStepModal) return true;
  // If Bootstrap is unavailable, we'll fallback later in the caller
  const html = buildDeleteStepModalHTML();
  document.body.insertAdjacentHTML("beforeend", html);
  // Refresh DOM references
  dom.deleteStepModal = document.getElementById("modal-delete-step");
  dom.deleteStepTitle = document.getElementById("delete-step-title");
  dom.deleteStepItems = document.getElementById("delete-step-items");
  dom.confirmDeleteStepBtn = document.getElementById("confirm-delete-step-btn");
  if (!dom.deleteStepModal) return false;
  bindDeleteStepModalEvents();
  return true;
};

const showDeleteStepModal = (stepCard) => {
  if (!stepCard) return;
  if (!dom.deleteStepModal) {
    // Try to create modal dynamically
    const created = createDeleteStepModalIfNeeded();
    if (!created || typeof bootstrap === "undefined" || !bootstrap.Modal) {
      // Fallback to native confirm if modal not available
      const confirmed = window.confirm(
        translate(
          "template.editor.delete_step_confirm",
          "Are you sure you want to delete this step?",
        ),
      );
      if (confirmed) {
        getStepSettings(stepCard).forEach((key) =>
          settingAssignments.delete(key),
        );
        getStepConfigs(stepCard).forEach((ref) =>
          configAssignments.delete(ref),
        );
        stepCard.remove();
        refreshStepOptions();
        reindexSteps();
        updateSummary();
      }
      return;
    }
  }

  // Ensure modal instance
  deleteStepModalInstance =
    deleteStepModalInstance || new bootstrap.Modal(dom.deleteStepModal);

  // Derive step display title and item counts
  const heading = stepCard.querySelector(".step-heading");
  const titleInput = stepCard.querySelector(".step-title");
  const rawTitle = heading?.textContent?.trim() || titleInput?.value?.trim();
  const displayTitle =
    rawTitle ||
    translate("template.editor.step_default_title", "Untitled step");

  const settingsCount = stepCard.querySelectorAll(
    ".step-settings-list .step-item",
  ).length;
  const configsCount = stepCard.querySelectorAll(
    ".step-configs-list .step-item",
  ).length;

  if (dom.deleteStepTitle) dom.deleteStepTitle.textContent = displayTitle;
  if (dom.deleteStepItems)
    dom.deleteStepItems.textContent = `${settingsCount} ${translate(
      "template.editor.settings",
      "settings",
    )}, ${configsCount} ${translate("template.editor.configs", "configs")}`;

  state.stepToDelete = stepCard;
  deleteStepModalInstance.show();
};

const configEditors = new Map();

const getThemePreference = () =>
  (document.getElementById("theme")?.value || "").trim().toLowerCase();

const resolveAceTheme = () =>
  getThemePreference() === "dark"
    ? "ace/theme/cloud9_night"
    : "ace/theme/cloud9_day";

const applyThemeToEditor = (editor) => {
  if (!editor || typeof window === "undefined" || !window.ace) return;
  editor.setTheme(resolveAceTheme());
};

const refreshConfigEditorThemes = () => {
  configEditors.forEach(({ editor }) => {
    applyThemeToEditor(editor);
  });
};

const setupThemeSync = () => {
  const darkModeToggle = document.getElementById("dark-mode-toggle");
  if (!darkModeToggle) return;
  darkModeToggle.addEventListener("change", () => {
    setTimeout(() => {
      refreshConfigEditorThemes();
    }, 50);
  });
};

const setConfigEditorMode = (editor, typeValue) => {
  if (!editor || typeof window === "undefined" || !window.ace) return;
  const mode = "ace/mode/nginx";
  editor.session.setMode(mode);
};

const ensureConfigEditor = (wrapper, initialValue = "", typeValue = "") => {
  if (
    !wrapper ||
    typeof window === "undefined" ||
    typeof window.ace === "undefined"
  )
    return null;

  const container = wrapper.querySelector(".config-data-editor");
  const textarea = wrapper.querySelector(".config-data");
  if (!container || !textarea) return null;

  const editor = window.ace.edit(container);
  editor.setOptions({
    fontSize: "14px",
    showPrintMargin: false,
    tabSize: 2,
    useSoftTabs: true,
    wrap: true,
    minLines: 10,
    maxLines: Infinity,
    autoScrollEditorIntoView: true,
  });
  editor.renderer.setScrollMargin(10, 10);
  editor.setValue(initialValue || "", -1);
  textarea.value = editor.getValue();
  applyThemeToEditor(editor);
  setConfigEditorMode(editor, typeValue);
  editor.resize(true);

  editor.session.on("change", () => {
    textarea.value = editor.getValue();
  });

  configEditors.set(wrapper.dataset.configId, {
    editor,
    textarea,
    container,
  });

  return editor;
};

const disposeConfigEditor = (wrapper) => {
  if (!wrapper) return;
  const entry = configEditors.get(wrapper.dataset.configId);
  if (!entry) return;
  if (entry.editor && typeof entry.editor.destroy === "function") {
    entry.editor.destroy();
  }
  if (entry.container) {
    entry.container.innerHTML = "";
  }
  configEditors.delete(wrapper.dataset.configId);
};

const settingAssignments = new Map();
const configAssignments = new Map();

const getDragAfterElement = (container, y) => {
  const items = Array.from(
    container.querySelectorAll(".step-item:not(.dragging)"),
  );
  return items.reduce(
    (closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset, element: child };
      }
      return closest;
    },
    { offset: Number.NEGATIVE_INFINITY, element: null },
  ).element;
};

const attachDragBehaviour = (item) => {
  if (!item) return;
  item.setAttribute("draggable", "true");
  item.addEventListener("dragstart", (event) => {
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", "");
    }
    item.classList.add("dragging");
    const originStep = item.closest(".step-card")?.dataset.stepId || "";
    item.dataset.dragOriginStep = originStep;
  });
  item.addEventListener("dragend", () => {
    item.classList.remove("dragging");
    delete item.dataset.dragOriginStep;
    document
      .querySelectorAll(".step-list-dragover")
      .forEach((node) => node.classList.remove("step-list-dragover"));
    updateStepListEmptyState(item.parentElement);
  });
};

const syncSettingAssignments = (list) => {
  const stepCard = list.closest(".step-card");
  if (!stepCard) return;
  const stepId = stepCard.dataset.stepId;
  Array.from(list.querySelectorAll(".step-item")).forEach((item) => {
    const key = item.dataset.key;
    if (key) {
      settingAssignments.set(key, stepId);
    }
  });
};

const syncConfigAssignments = (list) => {
  const stepCard = list.closest(".step-card");
  if (!stepCard) return;
  const stepId = stepCard.dataset.stepId;
  Array.from(list.querySelectorAll(".step-item")).forEach((item) => {
    const ref = item.dataset.ref;
    if (ref) {
      configAssignments.set(ref, stepId);
    }
  });
};

const updateStepListEmptyState = (list) => {
  if (!list) return;
  const placeholder = list.querySelector(".step-empty-state");
  if (!placeholder) return;
  const hasItems = list.querySelectorAll(".step-item").length > 0;
  placeholder.classList.toggle("d-none", hasItems);
};

function handleListReorder(list, type) {
  if (!list) return;
  const stepCard = list.closest(".step-card");
  if (type === "settings") {
    syncSettingAssignments(list);
    if (stepCard) updateStepSettingsButtonState(stepCard);
  } else if (type === "configs") {
    syncConfigAssignments(list);
    if (stepCard) updateStepConfigsButtonState(stepCard);
  }
  updateStepListEmptyState(list);
  refreshStepOptions();
  updateSummary();
}

const configureDraggableList = (list, { onReorder, type } = {}) => {
  if (!list || list.dataset.dragEnabled === "true") return;

  const isMatchingItem = (item) => {
    if (!item) return false;
    if (!type) return true;
    if (type === "settings") return Boolean(item.dataset.key);
    if (type === "configs") return Boolean(item.dataset.ref);
    return true;
  };

  list.addEventListener("dragover", (event) => {
    const dragging = document.querySelector(".step-item.dragging");
    if (!isMatchingItem(dragging)) return;
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "move";
    }
    list.classList.add("step-list-dragover");
    const afterElement = getDragAfterElement(list, event.clientY);
    if (!afterElement) {
      list.appendChild(dragging);
    } else if (afterElement !== dragging) {
      list.insertBefore(dragging, afterElement);
    }
  });

  list.addEventListener("dragleave", (event) => {
    if (!list.contains(event.relatedTarget)) {
      list.classList.remove("step-list-dragover");
    }
  });

  list.addEventListener("drop", (event) => {
    event.preventDefault();
    list.classList.remove("step-list-dragover");
    const dragging = document.querySelector(".step-item.dragging");
    if (dragging) dragging.classList.remove("dragging");
    if (!isMatchingItem(dragging)) return;

    if (type) {
      handleListReorder(list, type);
      const originStepId = dragging?.dataset?.dragOriginStep;
      const currentStepId = list.closest(".step-card")?.dataset.stepId;
      if (originStepId && originStepId !== currentStepId) {
        const originCard = dom.stepsList.querySelector(
          `.step-card[data-step-id="${originStepId}"]`,
        );
        if (originCard) {
          const originList = originCard.querySelector(
            type === "settings" ? ".step-settings-list" : ".step-configs-list",
          );
          if (originList) {
            handleListReorder(originList, type);
          }
        }
      }
    }

    if (dragging && dragging.dataset) {
      delete dragging.dataset.dragOriginStep;
    }

    if (!type) {
      updateStepListEmptyState(list);
    }

    if (typeof onReorder === "function") {
      onReorder();
    }
  });

  list.dataset.dragEnabled = "true";
};

const moveListItem = (item, direction, type) => {
  if (!item) return false;
  const list = item.parentElement;
  if (!list) return false;

  if (direction === "up") {
    const previous = item.previousElementSibling;
    if (!previous) return false;
    list.insertBefore(item, previous);
  } else if (direction === "down") {
    const next = item.nextElementSibling;
    if (!next) return false;
    list.insertBefore(item, next.nextElementSibling);
  } else {
    return false;
  }

  if (type) {
    handleListReorder(list, type);
  }
  return true;
};

const registerKeyboardReorder = (item, type) => {
  if (!item) return;
  item.setAttribute("aria-keyshortcuts", "Shift+ArrowUp Shift+ArrowDown");
  item.addEventListener("keydown", (event) => {
    const hasModifier =
      event.metaKey || event.ctrlKey || event.altKey || event.shiftKey;
    if ((event.key === "ArrowUp" || event.key === "ArrowDown") && hasModifier) {
      event.preventDefault();
      const direction = event.key === "ArrowUp" ? "up" : "down";
      const moved = moveListItem(item, direction, type);
      if (moved) {
        item.focus();
      }
    }
  });
};

const tryFulfilPendingSettingAssignment = (row) => {
  if (!row || !row.dataset) return false;
  const pendingStepId = row.dataset.pendingStepId;
  const key = row.dataset.settingKey;
  if (!pendingStepId || !key) return false;
  const stepCard = findStepCardById(pendingStepId);
  if (!stepCard) {
    delete row.dataset.pendingStepId;
    return false;
  }
  const assigned = assignSettingToStep(stepCard, key);
  if (assigned) {
    updateStepSettingsButtonState(stepCard);
    delete row.dataset.pendingStepId;
  }
  return assigned;
};

const tryFulfilPendingConfigAssignment = (row) => {
  if (!row || !row.dataset) return false;
  const pendingStepId = row.dataset.pendingStepId;
  const ref = row.dataset.ref;
  if (!pendingStepId || !ref) return false;
  const stepCard = findStepCardById(pendingStepId);
  if (!stepCard) {
    delete row.dataset.pendingStepId;
    return false;
  }
  const assigned = assignConfigToStep(stepCard, ref);
  if (assigned) {
    updateStepConfigsButtonState(stepCard);
    delete row.dataset.pendingStepId;
  }
  return assigned;
};

const getStepSettings = (stepCard) =>
  Array.from(stepCard.querySelectorAll(".step-settings-list .step-item")).map(
    (item) => item.dataset.key,
  );

const getStepConfigs = (stepCard) =>
  Array.from(stepCard.querySelectorAll(".step-configs-list .step-item")).map(
    (item) => item.dataset.ref,
  );

const findStepCardById = (stepId) =>
  dom.stepsList.querySelector(
    stepId ? `.step-card[data-step-id="${stepId}"]` : "",
  );

const toggleEmptyState = (container, placeholder) => {
  if (!container || !placeholder) return;
  const hasItems = container.children.length > 0;
  placeholder.classList.toggle("d-none", hasItems);
};

const getSettingKeys = () =>
  Array.from(dom.settingsList.querySelectorAll(".setting-key"))
    .map((input) => input.value.trim())
    .filter((value) => value.length > 0);

const getUsedSettingKeySet = () =>
  new Set(getSettingKeys().map((key) => normalizeSettingKey(key)));

const getSettingOrdering = (key) => {
  const entry = getCatalogEntry(key);
  if (!entry) {
    return {
      pluginOrder: 100000,
      settingOrder: 100000,
      label: key.toLowerCase(),
    };
  }
  return {
    pluginOrder: entry.pluginOrder,
    settingOrder: entry.settingOrder,
    label: entry.labelLower,
  };
};

const compareSettingKeys = (keyA, keyB) => {
  const orderA = getSettingOrdering(keyA);
  const orderB = getSettingOrdering(keyB);
  if (orderA.pluginOrder !== orderB.pluginOrder) {
    return orderA.pluginOrder - orderB.pluginOrder;
  }
  if (orderA.settingOrder !== orderB.settingOrder) {
    return orderA.settingOrder - orderB.settingOrder;
  }
  return orderA.label.localeCompare(orderB.label, undefined, {
    sensitivity: "base",
  });
};

const sortSettingRows = () => {
  if (!dom.settingsList) return;
  const rows = Array.from(dom.settingsList.querySelectorAll(".setting-row"));
  rows
    .map((row) => ({
      row,
      key:
        row.dataset.settingKey ||
        row.querySelector(".setting-key")?.value.trim() ||
        "",
    }))
    .sort((a, b) => compareSettingKeys(a.key, b.key))
    .forEach(({ row }) => dom.settingsList.append(row));
};

const ensureSettingSelectorModal = () => {
  if (settingSelectorModalInstance || !dom.settingSelectorModal) return;
  if (typeof bootstrap === "undefined" || !bootstrap.Modal) return;
  settingSelectorModalInstance = bootstrap.Modal.getOrCreateInstance(
    dom.settingSelectorModal,
    {},
  );
};

const closeSettingSelector = () => {
  if (!dom.settingSelectorModal) return;
  ensureSettingSelectorModal();
  settingSelectorModalInstance?.hide();
  if (dom.settingSelectorOpenBtn) {
    dom.settingSelectorOpenBtn.setAttribute("aria-expanded", "false");
  }
};

const openSettingSelector = () => {
  if (!dom.settingSelectorModal) return;
  ensureSettingSelectorModal();
  refreshSettingSelector({ maintainSelection: true });
  runTranslations();
  if (dom.settingSelectorOpenBtn) {
    dom.settingSelectorOpenBtn.setAttribute("aria-expanded", "true");
  }
  settingSelectorModalInstance?.show();
};

const updateSettingSelectorCount = (available, used) => {
  if (!dom.settingSelectorCount) return;
  const applyCountMessage = (key, fallback, options) => {
    dom.settingSelectorCount.textContent = translate(key, fallback, options);
    if (key) {
      dom.settingSelectorCount.setAttribute("data-i18n", key);
      if (options && Object.keys(options).length > 0) {
        dom.settingSelectorCount.setAttribute(
          "data-i18n-options",
          JSON.stringify(options),
        );
      } else {
        dom.settingSelectorCount.removeAttribute("data-i18n-options");
      }
    } else {
      dom.settingSelectorCount.removeAttribute("data-i18n");
      dom.settingSelectorCount.removeAttribute("data-i18n-options");
    }
  };
  if (!available && !used) {
    applyCountMessage(
      "template.editor.setting_selector_count_empty",
      "No settings to display.",
    );
    return;
  }
  if (!available && used) {
    applyCountMessage(
      "template.editor.setting_selector_count_all_used",
      "All matching settings have already been added.",
    );
    return;
  }
  if (available && !used) {
    applyCountMessage(
      "template.editor.setting_selector_count_only_available",
      available === 1
        ? "1 setting available"
        : `${available} settings available`,
      { count: available },
    );
    return;
  }
  applyCountMessage(
    "template.editor.setting_selector_count_with_used",
    `${available} available, ${used} already added`,
    { available, used },
  );
};

const highlightSettingSelectorOption = (
  key,
  { scrollIntoView = false } = {},
) => {
  if (!dom.settingSelectorResults) return;
  const normalizedKey = normalizeSettingKey(key);
  const options = dom.settingSelectorResults.querySelectorAll(
    ".setting-selector-option",
  );
  options.forEach((option) => {
    const optionKey = normalizeSettingKey(option.dataset.key || "");
    const isActive = optionKey && optionKey === normalizedKey;
    option.classList.toggle("active", isActive);
    option.setAttribute("aria-selected", isActive ? "true" : "false");
    if (isActive && scrollIntoView) {
      option.scrollIntoView({ block: "nearest" });
    }
  });
};

const settingSelectorMatchesQuery = (entry, tokens) => {
  if (!tokens.length) return { matched: true, score: entry.popularity };

  let score = entry.popularity;
  for (const token of tokens) {
    const needle = token.toLowerCase();
    const inKey = entry.keyLower.includes(needle);
    const inLabel = entry.labelLower.includes(needle);
    const inPlugin = entry.pluginNameLower.includes(needle);
    const inDescription = entry.descriptionLower.includes(needle);
    const inTags = entry.tagTokens.some((tag) => tag.includes(needle));

    if (!(inKey || inLabel || inPlugin || inDescription || inTags)) {
      return { matched: false, score: 0 };
    }

    if (entry.keyLower === needle) score += 400;
    else if (entry.keyLower.startsWith(needle)) score += 220;
    else if (inKey) score += 120;

    if (entry.labelLower === needle) score += 260;
    else if (entry.labelLower.startsWith(needle)) score += 160;
    else if (inLabel) score += 120;

    if (inPlugin) score += 80;
    if (inDescription) score += 40;
    if (inTags) score += 30;
  }

  return { matched: true, score };
};

const renderSettingSelectorResults = () => {
  if (!dom.settingSelectorResults) return;

  dom.settingSelectorResults.innerHTML = "";

  const availableCount = settingSelectorState.entries.filter(
    (item) => !item.used,
  ).length;
  const usedCount = settingSelectorState.entries.length - availableCount;

  updateSettingSelectorCount(availableCount, usedCount);

  if (settingSelectorState.entries.length === 0) {
    dom.settingSelectorResults.classList.add("d-none");
    dom.settingSelectorEmpty?.classList.remove("d-none");
    highlightSettingSelectorOption(null);
    return;
  }

  dom.settingSelectorResults.classList.remove("d-none");
  dom.settingSelectorEmpty?.classList.add("d-none");

  const fragment = document.createDocumentFragment();

  const defaultBadgeText = translate(
    "template.editor.setting_selector_default",
    "Default",
  );

  settingSelectorState.entries.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className =
      "list-group-item list-group-item-action setting-selector-option text-start";
    button.dataset.key = item.entry.key;
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", "false");

    if (item.used) {
      button.classList.add("disabled", "opacity-75");
      button.setAttribute("aria-disabled", "true");
    }

    const header = document.createElement("div");
    header.className =
      "d-flex justify-content-between align-items-center gap-2";

    const title = document.createElement("div");
    title.className = "fw-semibold text-body";
    title.textContent = item.entry.label || item.entry.key;

    const keyBadge = document.createElement("span");
    keyBadge.className = "badge bg-label-secondary text-uppercase";
    keyBadge.textContent = item.entry.key;

    header.append(title, keyBadge);
    button.append(header);

    const metaLine = document.createElement("div");
    metaLine.className =
      "d-flex flex-wrap align-items-center gap-2 small text-muted mt-1";

    const pluginBadge = document.createElement("span");
    pluginBadge.className =
      "badge rounded-pill bg-label-primary text-uppercase";
    pluginBadge.textContent = item.entry.pluginName;
    metaLine.append(pluginBadge);

    if (item.entry.pluginType && pluginTypeLabels[item.entry.pluginType]) {
      const typeBadge = document.createElement("span");
      typeBadge.className = "badge rounded-pill bg-label-info text-uppercase";
      typeBadge.textContent = pluginTypeLabels[item.entry.pluginType];
      metaLine.append(typeBadge);
    }

    if (item.entry.type) {
      const settingTypeBadge = document.createElement("span");
      settingTypeBadge.className =
        "badge rounded-pill bg-label-secondary text-uppercase";
      settingTypeBadge.textContent = item.entry.type;
      metaLine.append(settingTypeBadge);
    }

    if (item.entry.multiple) {
      const multipleBadge = document.createElement("span");
      multipleBadge.className =
        "badge rounded-pill bg-label-warning text-uppercase";
      multipleBadge.textContent = translate(
        "template.editor.setting_selector_multiple",
        "Multiple",
      );
      multipleBadge.setAttribute(
        "data-i18n",
        "template.editor.setting_selector_multiple",
      );
      metaLine.append(multipleBadge);
    }

    button.append(metaLine);

    if (item.entry.description) {
      const description = document.createElement("p");
      description.className = "mb-1 small text-muted";
      description.textContent = item.entry.description;
      button.append(description);
    }

    if (item.entry.defaultValue) {
      const defaultLine = document.createElement("div");
      defaultLine.className = "small text-muted";
      const defaultLabel = document.createElement("span");
      defaultLabel.className = "me-1";
      defaultLabel.textContent = defaultBadgeText;
      defaultLabel.setAttribute(
        "data-i18n",
        "template.editor.setting_selector_default",
      );
      defaultLabel.setAttribute("data-i18n-attr", "text");
      const defaultValue = document.createElement("code");
      defaultValue.textContent = item.entry.defaultValue;
      defaultLine.append(
        defaultLabel,
        document.createTextNode(": "),
        defaultValue,
      );
      button.append(defaultLine);
    }

    if (item.used) {
      const usedLabel = document.createElement("div");
      usedLabel.className = "small text-danger mt-1";
      usedLabel.textContent = translate(
        "template.editor.setting_selector_already_added",
        "Already added",
      );
      usedLabel.setAttribute(
        "data-i18n",
        "template.editor.setting_selector_already_added",
      );
      button.append(usedLabel);
    }

    button.addEventListener("click", (event) => {
      if (item.used) return;
      settingSelectorState.selectedKey = item.entry.key;
      highlightSettingSelectorOption(item.entry.key, {
        scrollIntoView: false,
      });
      updateSettingSelectorApplyState();
      if (event.detail && event.detail > 1) {
        commitSelectedSetting({ keepOpen: event.shiftKey });
      }
    });

    button.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !item.used) {
        event.preventDefault();
        settingSelectorState.selectedKey = item.entry.key;
        updateSettingSelectorApplyState();
        commitSelectedSetting({ keepOpen: event.shiftKey });
      }
    });

    fragment.append(button);
  });

  dom.settingSelectorResults.append(fragment);
  highlightSettingSelectorOption(settingSelectorState.selectedKey);
  runTranslations();
};

const updateSettingSelectorApplyState = () => {
  if (!dom.settingSelectorApply) return;
  if (!settingSelectorState.selectedKey) {
    dom.settingSelectorApply.setAttribute("disabled", "disabled");
    return;
  }
  const entry = getCatalogEntry(settingSelectorState.selectedKey);
  const usedKeys = getUsedSettingKeySet();
  const isUsed = usedKeys.has(
    normalizeSettingKey(settingSelectorState.selectedKey),
  );
  if (!entry || isUsed) {
    dom.settingSelectorApply.setAttribute("disabled", "disabled");
    return;
  }
  dom.settingSelectorApply.removeAttribute("disabled");
};

const refreshSettingSelector = ({ maintainSelection = true } = {}) => {
  if (!dom.settingSelectorResults) return;

  const usedKeys = getUsedSettingKeySet();
  const queryTokens = settingSelectorState.query
    .toLowerCase()
    .split(/\s+/)
    .filter((token) => token.length > 0);

  const pluginFilter = settingSelectorState.plugin;
  const typeFilter = settingSelectorState.type;

  const availableEntries = [];
  const usedEntries = [];

  settingsCatalog.forEach((entry) => {
    if (pluginFilter && entry.pluginId !== pluginFilter) return;
    if (typeFilter && entry.type !== typeFilter) return;

    const { matched, score } = settingSelectorMatchesQuery(entry, queryTokens);
    if (!matched) return;

    const isUsed = usedKeys.has(entry.keyUpper);
    const bucket = isUsed ? usedEntries : availableEntries;
    bucket.push({ entry, score, used: isUsed });
  });

  const rankEntries = (a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    if (a.entry.pluginOrder !== b.entry.pluginOrder) {
      return a.entry.pluginOrder - b.entry.pluginOrder;
    }
    if (a.entry.settingOrder !== b.entry.settingOrder) {
      return a.entry.settingOrder - b.entry.settingOrder;
    }
    const pluginCompare = a.entry.pluginNameLower.localeCompare(
      b.entry.pluginNameLower,
      undefined,
      { sensitivity: "base" },
    );
    if (pluginCompare) return pluginCompare;
    return a.entry.labelLower.localeCompare(b.entry.labelLower, undefined, {
      sensitivity: "base",
    });
  };

  availableEntries.sort(rankEntries);
  usedEntries.sort(rankEntries);

  const previousSelection = maintainSelection
    ? normalizeSettingKey(settingSelectorState.selectedKey)
    : "";

  settingSelectorState.entries = [...availableEntries, ...usedEntries];

  const selectionExists = settingSelectorState.entries.some(
    (item) =>
      !item.used && normalizeSettingKey(item.entry.key) === previousSelection,
  );

  if (!selectionExists) {
    const firstAvailable = settingSelectorState.entries.find(
      (item) => !item.used,
    );
    settingSelectorState.selectedKey = firstAvailable
      ? firstAvailable.entry.key
      : null;
  }

  renderSettingSelectorResults();
  updateSettingSelectorApplyState();
};

const moveSettingSelectorSelection = (direction) => {
  if (!settingSelectorState.entries.length) return;
  const normalizedSelected = normalizeSettingKey(
    settingSelectorState.selectedKey,
  );
  const selectable = settingSelectorState.entries.filter((item) => !item.used);
  if (!selectable.length) return;

  let currentIndex = selectable.findIndex(
    (item) => normalizeSettingKey(item.entry.key) === normalizedSelected,
  );

  if (currentIndex === -1) {
    currentIndex = direction > 0 ? -1 : 0;
  }

  let nextIndex;
  if (direction > 0) {
    nextIndex = currentIndex + 1;
    if (nextIndex >= selectable.length) nextIndex = 0;
  } else {
    nextIndex = currentIndex - 1;
    if (nextIndex < 0) nextIndex = selectable.length - 1;
  }

  const nextEntry = selectable[nextIndex];
  if (!nextEntry) return;

  settingSelectorState.selectedKey = nextEntry.entry.key;
  highlightSettingSelectorOption(nextEntry.entry.key, { scrollIntoView: true });
  updateSettingSelectorApplyState();
};

const handleSettingSelectorSearchKeydown = (event) => {
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    moveSettingSelectorSelection(event.key === "ArrowDown" ? 1 : -1);
    return;
  }
  if (event.key === "Enter") {
    const added = commitSelectedSetting({ keepOpen: event.shiftKey });
    if (added) {
      event.preventDefault();
    }
    return;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    closeSettingSelector();
  }
};

const addSettingFromCatalog = (entry, { keepOpen = false } = {}) => {
  if (!entry) return false;
  const usedKeys = getUsedSettingKeySet();
  if (usedKeys.has(entry.keyUpper)) return false;

  const newRow = createSettingRow({
    key: entry.key,
    value: entry.defaultValue || "",
    catalogEntry: entry,
  });

  if (!newRow) return false;

  if (!keepOpen) {
    closeSettingSelector();
  }

  const keyInput = newRow.querySelector(".setting-key");
  if (keyInput) {
    keyInput.focus({ preventScroll: false });
    keyInput.select();
  }

  newRow.scrollIntoView({ behavior: "smooth", block: "center" });
  sortSettingRows();
  return true;
};

const removeSettingRow = (wrapper) => {
  if (!wrapper) return;
  const keyInput = wrapper.querySelector(".setting-key");
  const settingKey = wrapper.dataset.settingKey || keyInput?.value.trim();
  let handledByStep = false;
  if (settingKey) {
    const owner = settingAssignments.get(settingKey);
    if (owner) {
      const ownerCard = findStepCardById(owner);
      if (ownerCard) {
        removeSettingFromStep(ownerCard, settingKey);
        handledByStep = true;
      } else {
        settingAssignments.delete(settingKey);
      }
    }
  }
  delete wrapper.settingControl;
  wrapper.remove();
  toggleEmptyState(dom.settingsList, dom.settingsEmpty);
  if (!handledByStep) {
    refreshStepOptions();
    updateSummary();
  }
  refreshSettingSelector({ maintainSelection: false });
  sortSettingRows();
  runTranslations();
};

const showSettingRemoveModal = (wrapper) => {
  if (!wrapper || !dom.settingRemoveModal) return;
  ensureSettingRemoveModal();

  const keyInput = wrapper.querySelector(".setting-key");
  const key = keyInput ? keyInput.value.trim() : wrapper.dataset.settingKey;
  const entry = getCatalogEntry(key);
  if (dom.settingRemoveName) {
    dom.settingRemoveName.textContent = entry?.label
      ? `${entry.label} (${key})`
      : key || "";
  }
  state.settingToRemove = wrapper;
  runTranslations();
  settingRemoveModalInstance?.show();
};

const commitSelectedSetting = ({ keepOpen = false } = {}) => {
  if (!settingSelectorState.selectedKey) return false;
  const entry = getCatalogEntry(settingSelectorState.selectedKey);
  if (!entry) return false;
  return addSettingFromCatalog(entry, { keepOpen });
};

const populateSettingSelectorFilters = () => {
  if (dom.settingSelectorPlugin) {
    const currentValue = dom.settingSelectorPlugin.value;
    dom.settingSelectorPlugin
      .querySelectorAll("option[data-generated]")
      .forEach((option) => option.remove());
    const fragment = document.createDocumentFragment();
    Array.from(pluginOptionMap.values())
      .sort((a, b) => a.order - b.order)
      .forEach((option) => {
        const opt = document.createElement("option");
        opt.value = option.id;
        opt.textContent = option.name;
        opt.dataset.generated = "true";
        if (option.type && pluginTypeLabels[option.type]) {
          opt.dataset.pluginTypeLabel = pluginTypeLabels[option.type];
        }
        fragment.append(opt);
      });
    dom.settingSelectorPlugin.append(fragment);
    dom.settingSelectorPlugin.value = currentValue;
  }

  if (dom.settingSelectorType) {
    const currentValue = dom.settingSelectorType.value;
    dom.settingSelectorType
      .querySelectorAll("option[data-generated]")
      .forEach((option) => option.remove());
    const fragment = document.createDocumentFragment();
    typeOptions.forEach((type) => {
      const opt = document.createElement("option");
      opt.value = type;
      opt.textContent = type;
      opt.dataset.generated = "true";
      fragment.append(opt);
    });
    dom.settingSelectorType.append(fragment);
    dom.settingSelectorType.value = currentValue;
  }

  runTranslations();
};

const normalizeConfigType = (rawType) =>
  (rawType || "").toString().trim().replace(/-/g, "_").toLowerCase();

const normalizeConfigName = (rawName) => {
  if (typeof rawName !== "string") return "";
  const trimmed = rawName.trim();
  if (!trimmed) return "";
  return trimmed.endsWith(".conf") ? trimmed.slice(0, -5) : trimmed;
};

const configTypeOptionsRaw = Array.isArray(ctx.multisiteConfigTypes)
  ? ctx.multisiteConfigTypes
  : [];

const configTypeOptions = configTypeOptionsRaw
  .map((item) => {
    if (!item) return null;
    if (typeof item === "string") {
      const normalized = normalizeConfigType(item);
      return {
        value: normalized,
        label: item,
        raw: item,
        description: "",
      };
    }
    const rawValue = item.value || item.id || item.raw || item.label || item;
    const normalized = normalizeConfigType(rawValue);
    if (!normalized) return null;
    return {
      value: normalized,
      label: item.label || item.raw || item.id || rawValue,
      raw: item.raw || item.id || rawValue,
      description: item.description || "",
    };
  })
  .filter((item) => item && item.value);

const allowedConfigTypeValues = new Set(
  configTypeOptions.map((option) => option.value),
);

const getConfigTypeMeta = (typeValue) => {
  const normalized = normalizeConfigType(typeValue);
  return configTypeOptions.find((option) => option.value === normalized);
};

const getConfigTypeDisplay = (typeValue) => {
  const meta = getConfigTypeMeta(typeValue);
  if (meta?.label) return meta.label;
  const normalized = normalizeConfigType(typeValue);
  return normalized ? normalized.toUpperCase() : "";
};

const getConfigTypeElements = (typeInput) => {
  const row = typeInput?.closest(".config-row");
  if (!row) return {};
  return {
    row,
    toggle: row.querySelector(".config-type-toggle"),
    label: row.querySelector(".config-type-label"),
    icon: row.querySelector(".config-type-icon"),
    menu: row.querySelectorAll(".config-type-menu button[data-value]"),
  };
};

const getConfigTypeIcon = (typeValue) => {
  const normalized = normalizeConfigType(typeValue);
  switch (normalized) {
    case "modsec_crs":
      return "bx-shield-alt";
    case "modsec":
      return "bx-shield-alt-2";
    case "server_stream":
      return "bx-network-chart";
    case "server_http":
      return "bx-network-chart";
    case "crs_plugins_before":
    case "crs_plugins_after":
      return "bx-shield-quarter";
    default:
      return "bx-window-alt";
  }
};

const setConfigTypeDisplay = (typeInput, typeValue) => {
  const elements = getConfigTypeElements(typeInput);
  const { row, toggle, label, icon, menu } = elements;
  const normalized = normalizeConfigType(typeValue);
  const meta = getConfigTypeMeta(normalized);
  const placeholder = row?.dataset.typePlaceholder || "Select a type";
  const displayLabel =
    meta?.label ||
    typeInput.dataset.displayLabel ||
    (normalized ? normalized.toUpperCase() : placeholder);

  if (label) {
    label.textContent = normalized ? displayLabel : placeholder;
    // When showing placeholder, keep i18n marker; otherwise remove it.
    if (!normalized) {
      label.setAttribute(
        "data-i18n",
        "template.editor.select_config_type_placeholder",
      );
    } else {
      label.removeAttribute("data-i18n");
    }
  }

  if (icon) {
    const iconClass = normalized
      ? getConfigTypeIcon(normalized)
      : "bx-window-alt text-muted";
    icon.className = `bx ${iconClass} config-type-icon`;
  }

  if (toggle) {
    toggle.classList.toggle("config-type-empty", !normalized);
  }

  if (menu && menu.length) {
    menu.forEach((button) => {
      button.classList.toggle(
        "active",
        normalizeConfigType(button.dataset.value) === normalized,
      );
    });
  }
};

const markConfigTypeValid = (typeInput) => {
  if (!typeInput) return;
  delete typeInput.dataset.invalidMessage;
  typeInput.classList.remove("is-invalid");

  const { toggle } = getConfigTypeElements(typeInput);
  if (!toggle) return;

  toggle.classList.remove("is-invalid", "btn-outline-danger");
  toggle.classList.add("btn-outline-primary");
  delete toggle.dataset.invalidMessage;
};

const markConfigTypeInvalid = (typeInput, message) => {
  if (!typeInput) return;
  typeInput.dataset.invalidMessage = message;
  typeInput.classList.add("is-invalid");

  const { toggle } = getConfigTypeElements(typeInput);
  if (!toggle) return;

  toggle.classList.remove("btn-outline-primary");
  toggle.classList.add("btn-outline-danger", "is-invalid");
  toggle.dataset.invalidMessage = message;
};

const buildConfigReference = (typeValue, nameValue) => {
  const type = normalizeConfigType(typeValue);
  const name = normalizeConfigName(nameValue);
  if (!type || !name) return "";
  return `${type}/${name}.conf`;
};

const getConfigDescriptors = () => {
  const descriptors = [];
  dom.configsList.querySelectorAll(".config-row").forEach((row) => {
    const typeInput = row.querySelector(".config-type");
    const nameInput = row.querySelector(".config-name");
    const ref = buildConfigReference(typeInput?.value, nameInput?.value);
    if (!ref) return;
    const [type, nameConf] = ref.split("/");
    const name = nameConf ? nameConf.replace(".conf", "") : ref;
    const displayType = getConfigTypeDisplay(type) || type;
    descriptors.push({ ref, display: `${displayType} / ${name}` });
  });
  return descriptors;
};

const replaceConfigReferenceInSteps = (oldRef, newRef) => {
  if (!oldRef || oldRef === newRef) return;

  const owner = configAssignments.get(oldRef);
  if (owner) {
    configAssignments.delete(oldRef);
    if (newRef) {
      configAssignments.set(newRef, owner);
    }
  }

  dom.stepsList
    .querySelectorAll(".step-configs-list .step-item")
    .forEach((item) => {
      if (item.dataset.ref !== oldRef) return;
      const stepCard = item.closest(".step-card");
      if (!stepCard) return;

      if (newRef) {
        item.dataset.ref = newRef;
        const [type, nameConf] = newRef.split("/");
        const name = nameConf ? nameConf.replace(".conf", "") : "";
        const label = item.querySelector(".step-item-label");
        if (label) label.textContent = `${type} / ${name}`;
        configAssignments.set(newRef, stepCard.dataset.stepId);
        updateStepConfigsButtonState(stepCard);
      } else {
        item.remove();
        updateStepConfigsButtonState(stepCard);
      }
      updateStepListEmptyState(stepCard.querySelector(".step-configs-list"));
    });

  refreshStepOptions();
  updateSummary();
};

const updateSummary = () => {
  if (counters.settings)
    counters.settings.textContent = getSettingKeys().length;
  if (counters.steps)
    counters.steps.textContent =
      dom.stepsList.querySelectorAll(".step-card").length;
  if (counters.configs)
    counters.configs.textContent =
      dom.configsList.querySelectorAll(".config-row").length;
};

const updateStepSettingsButtonState = (stepCard) => {
  const list = stepCard.querySelector(".step-settings-list");
  if (!list) return;
  const items = Array.from(list.querySelectorAll(".step-item"));
  items.forEach((item, index) => {
    const upBtn = item.querySelector(".step-item-move-up");
    const downBtn = item.querySelector(".step-item-move-down");
    if (upBtn) upBtn.disabled = index === 0;
    if (downBtn) downBtn.disabled = index === items.length - 1;
  });
};

const updateStepConfigsButtonState = (stepCard) => {
  const list = stepCard.querySelector(".step-configs-list");
  if (!list) return;
  const items = Array.from(list.querySelectorAll(".step-item"));
  items.forEach((item, index) => {
    const upBtn = item.querySelector(".step-item-move-up");
    const downBtn = item.querySelector(".step-item-move-down");
    if (upBtn) upBtn.disabled = index === 0;
    if (downBtn) downBtn.disabled = index === items.length - 1;
  });
};

const removeSettingFromStep = (stepCard, key) => {
  const list = stepCard.querySelector(".step-settings-list");
  if (!list) return;
  const item = Array.from(list.querySelectorAll(".step-item")).find(
    (node) => node.dataset.key === key,
  );
  if (!item) return;
  item.remove();
  settingAssignments.delete(key);
  updateStepSettingsButtonState(stepCard);
  updateStepListEmptyState(list);
  refreshStepOptions();
  updateSummary();
};

const removeConfigFromStep = (stepCard, ref) => {
  const list = stepCard.querySelector(".step-configs-list");
  if (!list) return;
  const item = Array.from(list.querySelectorAll(".step-item")).find(
    (node) => node.dataset.ref === ref,
  );
  if (!item) return;
  item.remove();
  configAssignments.delete(ref);
  updateStepConfigsButtonState(stepCard);
  updateStepListEmptyState(list);
  refreshStepOptions();
  updateSummary();
};

const createSettingListItem = (stepCard, key) => {
  const list = stepCard.querySelector(".step-settings-list");
  if (!list) return null;

  const item = document.createElement("div");
  item.className =
    "list-group-item step-item d-flex align-items-center justify-content-between flex-wrap gap-2";
  item.dataset.key = key;
  item.setAttribute("role", "listitem");
  item.tabIndex = 0;

  const content = document.createElement("div");
  content.className =
    "d-flex align-items-center gap-2 flex-grow-1 flex-wrap text-truncate";

  const handle = document.createElement("span");
  handle.className = "step-item-handle d-flex align-items-center text-muted";
  handle.innerHTML = '<i class="bx bx-dots-vertical-rounded"></i>';
  handle.title = translate("template.editor.drag_handle", "Drag to reorder");
  handle.setAttribute("data-i18n-title", "template.editor.drag_handle");
  handle.setAttribute("aria-hidden", "true");

  const labelWrapper = document.createElement("div");
  labelWrapper.className = "d-flex align-items-center gap-2 text-truncate";

  const labelIcon = document.createElement("i");
  labelIcon.className = "bx bx-slider";

  const label = document.createElement("span");
  label.className = "step-item-label";
  label.textContent = key;

  labelWrapper.append(labelIcon, label);
  content.append(handle, labelWrapper);

  const controls = document.createElement("div");
  controls.className = "d-flex align-items-center gap-2 flex-wrap ms-auto";

  const moveGroup = document.createElement("div");
  moveGroup.className = "d-flex align-items-center gap-1 step-item-move-group";

  const moveUpBtn = document.createElement("button");
  moveUpBtn.type = "button";
  moveUpBtn.className = "btn btn-sm btn-outline-secondary step-item-move-up";
  moveUpBtn.innerHTML = '<i class="bx bx-chevron-up"></i>';
  moveUpBtn.title = translate("template.editor.button_move_up", "Move up");
  moveUpBtn.setAttribute("data-i18n-title", "template.editor.button_move_up");
  moveUpBtn.addEventListener("click", () => {
    moveListItem(item, "up", "settings");
  });

  const moveDownBtn = document.createElement("button");
  moveDownBtn.type = "button";
  moveDownBtn.className =
    "btn btn-sm btn-outline-secondary step-item-move-down";
  moveDownBtn.innerHTML = '<i class="bx bx-chevron-down"></i>';
  moveDownBtn.title = translate(
    "template.editor.button_move_down",
    "Move down",
  );
  moveDownBtn.setAttribute(
    "data-i18n-title",
    "template.editor.button_move_down",
  );
  moveDownBtn.addEventListener("click", () => {
    moveListItem(item, "down", "settings");
  });

  moveGroup.append(moveUpBtn, moveDownBtn);

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "btn btn-outline-danger btn-sm";
  removeBtn.innerHTML = '<i class="bx bx-trash"></i>';
  removeBtn.title = translate("template.editor.button_remove", "Remove");
  removeBtn.setAttribute("data-i18n-title", "template.editor.button_remove");
  removeBtn.addEventListener("click", () => {
    removeSettingFromStep(stepCard, key);
  });

  controls.append(moveGroup, removeBtn);

  item.append(content, controls);
  list.appendChild(item);

  attachDragBehaviour(item);
  configureDraggableList(list, { type: "settings" });
  registerKeyboardReorder(item, "settings");
  updateStepListEmptyState(list);

  return item;
};

const createConfigListItem = (stepCard, descriptor) => {
  const list = stepCard.querySelector(".step-configs-list");
  if (!list) return null;

  const item = document.createElement("div");
  item.className =
    "list-group-item step-item d-flex align-items-center justify-content-between flex-wrap gap-2";
  item.dataset.ref = descriptor.ref;
  item.setAttribute("role", "listitem");
  item.tabIndex = 0;

  const content = document.createElement("div");
  content.className =
    "d-flex align-items-center gap-2 flex-grow-1 flex-wrap text-truncate";

  const handle = document.createElement("span");
  handle.className = "step-item-handle d-flex align-items-center text-muted";
  handle.innerHTML = '<i class="bx bx-dots-vertical-rounded"></i>';
  handle.title = translate("template.editor.drag_handle", "Drag to reorder");
  handle.setAttribute("data-i18n-title", "template.editor.drag_handle");
  handle.setAttribute("aria-hidden", "true");

  const labelWrapper = document.createElement("div");
  labelWrapper.className = "d-flex align-items-center gap-2 text-truncate";

  const labelIcon = document.createElement("i");
  labelIcon.className = "bx bx-code-block";

  const label = document.createElement("span");
  label.className = "step-item-label";
  label.textContent = descriptor.display || descriptor.ref;

  labelWrapper.append(labelIcon, label);
  content.append(handle, labelWrapper);

  const controls = document.createElement("div");
  controls.className = "d-flex align-items-center gap-2 flex-wrap ms-auto";

  const moveGroup = document.createElement("div");
  moveGroup.className = "d-flex align-items-center gap-1 step-item-move-group";

  const moveUpBtn = document.createElement("button");
  moveUpBtn.type = "button";
  moveUpBtn.className = "btn btn-sm btn-outline-secondary step-item-move-up";
  moveUpBtn.innerHTML = '<i class="bx bx-chevron-up"></i>';
  moveUpBtn.title = translate("template.editor.button_move_up", "Move up");
  moveUpBtn.setAttribute("data-i18n-title", "template.editor.button_move_up");
  moveUpBtn.addEventListener("click", () => {
    moveListItem(item, "up", "configs");
  });

  const moveDownBtn = document.createElement("button");
  moveDownBtn.type = "button";
  moveDownBtn.className =
    "btn btn-sm btn-outline-secondary step-item-move-down";
  moveDownBtn.innerHTML = '<i class="bx bx-chevron-down"></i>';
  moveDownBtn.title = translate(
    "template.editor.button_move_down",
    "Move down",
  );
  moveDownBtn.setAttribute(
    "data-i18n-title",
    "template.editor.button_move_down",
  );
  moveDownBtn.addEventListener("click", () => {
    moveListItem(item, "down", "configs");
  });

  moveGroup.append(moveUpBtn, moveDownBtn);

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "btn btn-outline-danger btn-sm";
  removeBtn.innerHTML = '<i class="bx bx-trash"></i>';
  removeBtn.title = translate("template.editor.button_remove", "Remove");
  removeBtn.setAttribute("data-i18n-title", "template.editor.button_remove");
  removeBtn.addEventListener("click", () => {
    removeConfigFromStep(stepCard, descriptor.ref);
  });

  controls.append(moveGroup, removeBtn);

  item.append(content, controls);
  list.appendChild(item);

  attachDragBehaviour(item);
  configureDraggableList(list, { type: "configs" });
  registerKeyboardReorder(item, "configs");
  updateStepListEmptyState(list);

  return item;
};

const assignSettingToStep = (
  stepCard,
  key,
  { skipRefresh = false, skipSummary = false } = {},
) => {
  if (!key) return false;
  const stepId = stepCard.dataset.stepId;
  const currentOwner = settingAssignments.get(key);
  if (currentOwner && currentOwner !== stepId) {
    return false;
  }

  const list = stepCard.querySelector(".step-settings-list");
  if (!list) return false;

  if (
    Array.from(list.querySelectorAll(".step-item")).some(
      (item) => item.dataset.key === key,
    )
  ) {
    return true;
  }

  createSettingListItem(stepCard, key);
  settingAssignments.set(key, stepId);
  updateStepSettingsButtonState(stepCard);

  if (!skipRefresh) refreshStepOptions();
  if (!skipSummary) updateSummary();
  return true;
};

const assignConfigToStep = (
  stepCard,
  ref,
  { skipRefresh = false, skipSummary = false } = {},
) => {
  const canonicalRef = (ref || "").trim();
  if (!canonicalRef) return false;

  const descriptor = getConfigDescriptors().find(
    ({ ref: descriptorRef }) => descriptorRef === canonicalRef,
  );
  if (!descriptor) return false;

  const stepId = stepCard.dataset.stepId;
  const currentOwner = configAssignments.get(canonicalRef);
  if (currentOwner && currentOwner !== stepId) {
    return false;
  }

  const list = stepCard.querySelector(".step-configs-list");
  if (!list) return false;

  if (
    Array.from(list.querySelectorAll(".step-item")).some(
      (item) => item.dataset.ref === canonicalRef,
    )
  ) {
    return true;
  }

  createConfigListItem(stepCard, descriptor);
  configAssignments.set(canonicalRef, stepId);
  updateStepConfigsButtonState(stepCard);

  if (!skipRefresh) refreshStepOptions();
  if (!skipSummary) updateSummary();
  return true;
};

const refreshStepOptions = () => {
  const availableSettings = getSettingKeys().filter(
    (key) => !settingAssignments.has(key),
  );
  const availableConfigs = getConfigDescriptors().filter(
    ({ ref }) => !configAssignments.has(ref),
  );

  dom.stepsList.querySelectorAll(".step-card").forEach((card) => {
    const settingsSelect = card.querySelector(".step-settings-select");
    if (settingsSelect) {
      const previousValue = settingsSelect.value;
      settingsSelect.innerHTML = "";
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.disabled = true;
      placeholder.textContent = translate(
        "template.editor.select_setting_placeholder",
        "Select a setting",
      );
      placeholder.setAttribute(
        "data-i18n",
        "template.editor.select_setting_placeholder",
      );
      settingsSelect.appendChild(placeholder);
      availableSettings.forEach((key) => {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = key;
        settingsSelect.appendChild(option);
      });
      if (availableSettings.includes(previousValue)) {
        settingsSelect.value = previousValue;
      } else {
        settingsSelect.value = "";
        if (settingsSelect.options.length > 0) {
          settingsSelect.selectedIndex = 0;
        }
      }
      const noOptions = availableSettings.length === 0;
      settingsSelect.disabled = noOptions;
      const settingsAddButton = card.querySelector(".step-settings-add");
      if (settingsAddButton) {
        settingsAddButton.disabled = noOptions || !settingsSelect.value;
      }
    }

    const configsSelect = card.querySelector(".step-configs-select");
    if (configsSelect) {
      const previousValue = configsSelect.value;
      configsSelect.innerHTML = "";
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.disabled = true;
      placeholder.textContent = translate(
        "template.editor.select_config_placeholder",
        "Select a config",
      );
      placeholder.setAttribute(
        "data-i18n",
        "template.editor.select_config_placeholder",
      );
      configsSelect.appendChild(placeholder);
      availableConfigs.forEach(({ ref, display }) => {
        const option = document.createElement("option");
        option.value = ref;
        option.textContent = display;
        configsSelect.appendChild(option);
      });
      if (availableConfigs.some(({ ref }) => ref === previousValue)) {
        configsSelect.value = previousValue;
      } else {
        configsSelect.value = "";
        if (configsSelect.options.length > 0) {
          configsSelect.selectedIndex = 0;
        }
      }
      const noConfigOptions = availableConfigs.length === 0;
      configsSelect.disabled = noConfigOptions;
      const configsAddButton = card.querySelector(".step-configs-add");
      if (configsAddButton) {
        configsAddButton.disabled = noConfigOptions || !configsSelect.value;
      }
    }
  });
};

const showFeedback = (type, messages) => {
  if (!dom.feedback) return;
  const list = Array.isArray(messages) ? messages : [messages];
  dom.feedback.className = `alert alert-${type}`;
  if (list.length > 1) {
    dom.feedback.innerHTML = `<ul class="mb-0">${list
      .map((msg) => `<li>${msg}</li>`)
      .join("")}</ul>`;
  } else {
    dom.feedback.innerHTML = list[0];
  }
  dom.feedback.classList.remove("d-none");
  dom.feedback.scrollIntoView({ behavior: "smooth", block: "center" });
};

const clearFeedback = () => {
  if (!dom.feedback) return;
  dom.feedback.className = "alert d-none";
  dom.feedback.textContent = "";
};

const setSaving = (saving) => {
  if (!dom.saveButton) return;
  state.isSaving = saving;
  if (saving) {
    dom.saveButton.classList.add("disabled");
    dom.saveButton.setAttribute("disabled", "disabled");
    dom.saveButton.dataset.originalLabel = dom.saveButton.innerHTML;
    dom.saveButton.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>${translate(
      "button.save",
      "Save",
    )}`;
  } else {
    dom.saveButton.classList.remove("disabled");
    dom.saveButton.removeAttribute("disabled");
    if (dom.saveButton.dataset.originalLabel) {
      dom.saveButton.innerHTML = dom.saveButton.dataset.originalLabel;
    }
  }
};

const smoothScrollTo = (selector) => {
  if (!selector) return;
  const target = document.querySelector(selector);
  if (!target) return;
  const headerOffset = 100;
  const position =
    target.getBoundingClientRect().top + window.pageYOffset - headerOffset;
  window.scrollTo({ top: position < 0 ? 0 : position, behavior: "smooth" });
};

const updateSettingRowMeta = (container, entry) => {
  if (!container) return;
  container.innerHTML = "";
  if (!entry) {
    container.classList.add("d-none");
    container.dataset.catalogKey = "";
    return;
  }

  container.classList.remove("d-none");
  container.dataset.catalogKey = entry.key;

  const badges = document.createElement("div");
  badges.className = "d-flex flex-wrap align-items-center gap-1 mb-1";

  const pluginBadge = document.createElement("span");
  pluginBadge.className = "badge bg-label-primary text-uppercase";
  pluginBadge.textContent = entry.pluginName;
  badges.append(pluginBadge);

  if (entry.pluginType && pluginTypeLabels[entry.pluginType]) {
    const typeBadge = document.createElement("span");
    typeBadge.className = "badge bg-label-info text-uppercase";
    typeBadge.textContent = pluginTypeLabels[entry.pluginType];
    badges.append(typeBadge);
  }

  if (entry.type) {
    const dataTypeBadge = document.createElement("span");
    dataTypeBadge.className = "badge bg-label-secondary text-uppercase";
    dataTypeBadge.textContent = entry.type;
    badges.append(dataTypeBadge);
  }

  if (entry.multiple) {
    const multipleBadge = document.createElement("span");
    multipleBadge.className = "badge bg-label-warning text-uppercase";
    multipleBadge.textContent = translate(
      "template.editor.setting_selector_multiple",
      "Multiple",
    );
    badges.append(multipleBadge);
  }

  if (entry.advanced) {
    const advancedBadge = document.createElement("span");
    advancedBadge.className = "badge bg-label-dark text-uppercase";
    advancedBadge.textContent = translate(
      "template.editor.setting_selector_advanced",
      "Advanced",
    );
    badges.append(advancedBadge);
  }

  container.append(badges);

  if (entry.label && entry.label !== entry.key) {
    const labelLine = document.createElement("div");
    labelLine.className = "fw-semibold text-body";
    labelLine.textContent = entry.label;
    container.append(labelLine);
  }

  if (entry.description) {
    const description = document.createElement("div");
    description.className = "text-muted";
    description.textContent = entry.description;
    container.append(description);
  }

  if (Object.prototype.hasOwnProperty.call(entry, "default")) {
    const defaultLine = document.createElement("div");
    defaultLine.className = "small text-muted mt-1";
    const defaultLabel = document.createElement("span");
    defaultLabel.className = "me-1";
    defaultLabel.textContent = `${translate(
      "template.editor.setting_selector_default",
      "Default",
    )}:`;
    const defaultValue = document.createElement("code");
    const displayDefault =
      typeof entry.defaultValue === "string"
        ? entry.defaultValue
        : entry.default === null || typeof entry.default === "undefined"
          ? ""
          : String(entry.default);
    defaultValue.textContent = displayDefault;
    defaultLine.append(defaultLabel, defaultValue);
    container.append(defaultLine);
  }

  if (entry.regex) {
    const regexLine = document.createElement("div");
    regexLine.className = "small text-muted mt-1";
    const regexLabel = document.createElement("span");
    regexLabel.className = "me-1";
    regexLabel.textContent = `${translate(
      "template.editor.setting_selector_pattern",
      "Pattern",
    )}:`;
    const regexValue = document.createElement("code");
    regexValue.textContent = entry.regex;
    regexLine.append(regexLabel, regexValue);
    container.append(regexLine);
  }

  if (entry.docs) {
    const docsLine = document.createElement("div");
    docsLine.className = "small mt-2";
    const docsLink = document.createElement("a");
    docsLink.href = entry.docs;
    docsLink.target = "_blank";
    docsLink.rel = "noopener noreferrer";
    docsLink.className = "link-primary";
    docsLink.textContent = translate(
      "template.editor.setting_selector_docs",
      "View documentation",
    );
    docsLine.append(docsLink);
    container.append(docsLine);
  }
};

const createSettingRow = ({
  key = "",
  value = "",
  pendingStepId = "",
  catalogEntry = null,
} = {}) => {
  state.settingCounter += 1;
  const wrapper = document.createElement("article");
  wrapper.className = "card shadow-sm border-0 setting-row";
  wrapper.dataset.settingId = `setting-${state.settingCounter}`;
  if (pendingStepId) {
    wrapper.dataset.pendingStepId = pendingStepId;
  }

  const body = document.createElement("div");
  body.className = "card-body p-3";

  const row = document.createElement("div");
  row.className = "row g-3 align-items-start";

  const keyCol = document.createElement("div");
  keyCol.className = "col-12 col-lg-6";
  const settingId = `${wrapper.dataset.settingId}-key`;
  const resolvedEntry = catalogEntry || getCatalogEntry(key);

  const keyLabel = document.createElement("label");
  keyLabel.className = "form-label";
  keyLabel.setAttribute("data-i18n", "template.editor.label_setting_key");
  keyLabel.setAttribute("for", settingId);
  keyLabel.textContent = translate(
    "template.editor.label_setting_key",
    "Setting key",
  );
  const keyInput = document.createElement("input");
  keyInput.type = "text";
  keyInput.className = "form-control setting-key";
  keyInput.value = key;
  keyInput.required = true;
  keyInput.placeholder = translate(
    "template.editor.placeholder_setting_key",
    "Key",
  );
  keyInput.setAttribute(
    "data-i18n-placeholder",
    "template.editor.placeholder_setting_key",
  );
  keyInput.id = settingId;
  keyInput.addEventListener("input", () => {
    keyInput.classList.remove("is-invalid");
    const previousKey = wrapper.dataset.settingKey || "";
    const newKey = keyInput.value.trim();
    if (previousKey === newKey) return;

    const previousOwner = previousKey
      ? settingAssignments.get(previousKey)
      : null;
    if (previousKey && previousOwner) {
      const ownerCard = findStepCardById(previousOwner);
      if (ownerCard) {
        removeSettingFromStep(ownerCard, previousKey);
      } else {
        settingAssignments.delete(previousKey);
      }
    } else if (previousKey) {
      settingAssignments.delete(previousKey);
    }

    wrapper.dataset.settingKey = newKey;

    if (newKey && previousOwner) {
      const ownerCard = findStepCardById(previousOwner);
      if (ownerCard) {
        assignSettingToStep(ownerCard, newKey, {
          skipRefresh: true,
          skipSummary: true,
        });
        updateStepSettingsButtonState(ownerCard);
      }
    }

    const handledByPendingStep = tryFulfilPendingSettingAssignment(wrapper);
    if (!handledByPendingStep) {
      refreshStepOptions();
      updateSummary();
    }
    const catalogMatch = getCatalogEntry(newKey);
    if (catalogMatch) {
      wrapper.dataset.catalogKey = catalogMatch.key;
      wrapper.dataset.settingType = catalogMatch.type || "";
    } else {
      delete wrapper.dataset.catalogKey;
      delete wrapper.dataset.settingType;
    }
    const currentValue = wrapper.settingControl
      ? getSettingControlValue(wrapper.settingControl)
      : "";
    updateSettingControl(wrapper.settingControl, {
      entry: catalogMatch,
      value: currentValue,
    });
    syncValueLabelTarget();
    updateSettingRowMeta(metaContainer, catalogMatch);
    refreshSettingSelector({ maintainSelection: true });
    sortSettingRows();
    runTranslations();
  });
  keyCol.append(keyLabel, keyInput);

  const metaContainer = document.createElement("div");
  metaContainer.className = "setting-meta small text-muted mt-2";
  keyCol.append(metaContainer);

  const valueCol = document.createElement("div");
  valueCol.className = "col-12 col-lg-6";
  const valueLabel = document.createElement("label");
  valueLabel.className = "form-label";
  valueLabel.setAttribute("data-i18n", "template.editor.label_setting_value");
  valueLabel.textContent = translate(
    "template.editor.label_setting_value",
    "Default value",
  );
  valueCol.append(valueLabel);

  const valueContainer = document.createElement("div");
  valueContainer.className = "setting-value-wrapper";
  valueCol.append(valueContainer);

  const syncValueLabelTarget = () => {
    let target = valueContainer.querySelector(
      '.setting-value:not([type="hidden"])',
    );
    if (!target) {
      target = valueContainer.querySelector(
        "input.form-check-input, select, textarea",
      );
    }
    if (target && target.tagName !== "BUTTON") {
      if (!target.id) {
        target.id = `${wrapper.dataset.settingId}-value`;
      }
      valueLabel.setAttribute("for", target.id);
    } else {
      valueLabel.removeAttribute("for");
    }
  };

  const actionsCol = document.createElement("div");
  actionsCol.className =
    "col-12 col-lg-auto setting-actions d-flex justify-content-start justify-content-lg-end";
  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className =
    "btn btn-outline-danger btn-sm d-inline-flex align-items-center gap-1 setting-remove-btn";
  removeBtn.innerHTML = `<i class="bx bx-trash"></i><span class="d-none d-sm-inline" data-i18n="button.delete">${translate(
    "button.delete",
    "Delete",
  )}</span>`;
  removeBtn.title = translate("button.delete", "Delete");
  removeBtn.setAttribute("data-i18n-title", "button.delete");
  removeBtn.addEventListener("click", () => {
    showSettingRemoveModal(wrapper);
  });
  actionsCol.append(removeBtn);

  row.append(keyCol, valueCol, actionsCol);
  body.append(row);
  wrapper.append(body);
  dom.settingsList.append(wrapper);
  wrapper.dataset.settingKey = (key || "").trim();
  if (resolvedEntry) {
    wrapper.dataset.catalogKey = resolvedEntry.key;
    wrapper.dataset.settingType = resolvedEntry.type || "";
  } else {
    delete wrapper.dataset.catalogKey;
    delete wrapper.dataset.settingType;
  }
  const settingControl = createSettingControl({
    entry: resolvedEntry,
    value,
    settingId: wrapper.dataset.settingId,
    translate,
  });
  valueContainer.append(settingControl.root);
  wrapper.settingControl = settingControl;
  syncValueLabelTarget();
  updateSettingRowMeta(metaContainer, resolvedEntry);
  toggleEmptyState(dom.settingsList, dom.settingsEmpty);
  refreshStepOptions();
  updateSummary();
  tryFulfilPendingSettingAssignment(wrapper);
  refreshSettingSelector({ maintainSelection: true });
  sortSettingRows();
  runTranslations();
  return wrapper;
};

const createConfigRow = ({
  type = "",
  name = "",
  data = "",
  pendingStepId = "",
} = {}) => {
  state.configCounter += 1;
  const wrapper = document.createElement("article");
  wrapper.className = "card shadow-sm border-0 config-row";
  wrapper.dataset.configId = `config-${state.configCounter}`;
  if (pendingStepId) {
    wrapper.dataset.pendingStepId = pendingStepId;
  }

  const body = document.createElement("div");
  body.className = "card-body p-3";

  const row = document.createElement("div");
  row.className = "row g-3 align-items-center";

  const typeCol = document.createElement("div");
  typeCol.className = "col-12 col-xl-5";
  const typeLabel = document.createElement("label");
  typeLabel.className = "form-label";
  typeLabel.textContent = translate(
    "template.editor.label_config_type",
    "Type",
  );
  typeLabel.setAttribute("data-i18n", "template.editor.label_config_type");
  const typePlaceholder = translate(
    "template.editor.select_config_type_placeholder",
    "Select a type",
  );
  const incompatibleTypeMessage = translate(
    "template.editor.validation_config_type_multisite",
    "Config type must be one of the multisite-compatible types.",
  );
  const normalizedInitialType = normalizeConfigType(type);
  const initialMeta = getConfigTypeMeta(normalizedInitialType);

  let typeInput;
  if (configTypeOptions.length > 0) {
    typeInput = document.createElement("input");
    typeInput.type = "hidden";
    typeInput.className = "config-type";
    typeInput.value = normalizedInitialType;
    typeInput.dataset.displayLabel =
      initialMeta?.label || (type || "").toString();

    const dropdownWrapper = document.createElement("div");
    dropdownWrapper.className = "dropdown w-100";

    const typeToggle = document.createElement("button");
    typeToggle.type = "button";
    typeToggle.className =
      "btn btn-outline-primary dropdown-toggle w-100 d-flex align-items-center justify-content-between config-type-toggle";
    typeToggle.dataset.bsToggle = "dropdown";
    typeToggle.dataset.bsAutoClose = "outside";
    typeToggle.setAttribute("aria-expanded", "false");

    const toggleContent = document.createElement("span");
    toggleContent.className =
      "d-flex align-items-center gap-2 flex-grow-1 text-start";

    const typeIcon = document.createElement("i");
    typeIcon.className = "bx bx-window-alt config-type-icon";

    const typeLabelText = document.createElement("span");
    typeLabelText.className = "config-type-label text-truncate";
    typeLabelText.textContent = typePlaceholder;

    toggleContent.append(typeIcon, typeLabelText);
    typeToggle.append(toggleContent);

    const typeMenu = document.createElement("ul");
    typeMenu.className =
      "dropdown-menu nav-pills max-vh-60 overflow-auto pt-0 config-type-menu";
    typeMenu.setAttribute("role", "menu");

    const selectOption = (option) => {
      typeInput.value = option?.value || "";
      typeInput.dataset.displayLabel =
        option?.label || option?.raw || getConfigTypeDisplay(option?.value);
      typeInput.dispatchEvent(new Event("input", { bubbles: true }));
      typeInput.dispatchEvent(new Event("change", { bubbles: true }));
      if (typeof bootstrap !== "undefined" && bootstrap.Dropdown) {
        const instance =
          bootstrap.Dropdown.getInstance(typeToggle) ||
          bootstrap.Dropdown.getOrCreateInstance(typeToggle);
        if (instance) instance.hide();
      }
    };

    configTypeOptions.forEach((option) => {
      const item = document.createElement("li");
      item.className = "nav-item";

      const button = document.createElement("button");
      button.type = "button";
      button.className = "dropdown-item d-flex align-items-center gap-2";
      button.dataset.value = option.value;

      const optionIcon = document.createElement("i");
      optionIcon.className = `bx ${getConfigTypeIcon(option.value)}`;

      const optionLabel = document.createElement("span");
      optionLabel.textContent =
        option.label || option.raw || option.value.toUpperCase();

      button.append(optionIcon, optionLabel);
      button.addEventListener("click", () => selectOption(option));

      item.append(button);
      typeMenu.append(item);
    });

    dropdownWrapper.append(typeToggle, typeMenu);
    typeCol.append(typeLabel, dropdownWrapper, typeInput);
    wrapper.dataset.typePlaceholder = typePlaceholder;

    queueMicrotask(() => {
      if (typeof bootstrap !== "undefined" && bootstrap.Dropdown) {
        bootstrap.Dropdown.getOrCreateInstance(typeToggle);
      }
      applyTypeValidation();
    });
  } else {
    typeInput = document.createElement("input");
    typeInput.type = "text";
    typeInput.className = "form-control config-type";
    typeInput.value = type;
    typeInput.placeholder = typePlaceholder;
    typeInput.setAttribute(
      "data-i18n-placeholder",
      "template.editor.select_config_type_placeholder",
    );
    typeCol.append(typeLabel, typeInput);
  }

  const applyTypeValidation = () => {
    if (!typeInput.value) {
      markConfigTypeValid(typeInput);
      setConfigTypeDisplay(typeInput, typeInput.value);
      return;
    }
    const normalizedValue = normalizeConfigType(typeInput.value);
    const isAllowed =
      allowedConfigTypeValues.size === 0 ||
      allowedConfigTypeValues.has(normalizedValue);
    if (!isAllowed) {
      markConfigTypeInvalid(typeInput, incompatibleTypeMessage);
    } else {
      markConfigTypeValid(typeInput);
    }
    setConfigTypeDisplay(typeInput, typeInput.value);
    const editorEntry = configEditors.get(wrapper.dataset.configId);
    if (editorEntry?.editor) {
      setConfigEditorMode(editorEntry.editor, typeInput.value);
    }
  };

  const handleTypeChange = () => {
    const normalizedValue = normalizeConfigType(typeInput.value);
    if (normalizedValue) {
      const meta = getConfigTypeMeta(normalizedValue);
      if (meta?.label) {
        typeInput.dataset.displayLabel = meta.label;
      } else {
        typeInput.dataset.displayLabel = getConfigTypeDisplay(normalizedValue);
      }
    } else {
      delete typeInput.dataset.displayLabel;
    }

    const nameField = wrapper.querySelector(".config-name");
    const previousRef = wrapper.dataset.ref || "";
    const nextRef = buildConfigReference(typeInput.value, nameField?.value);
    if (previousRef && previousRef !== nextRef) {
      replaceConfigReferenceInSteps(previousRef, nextRef);
    }
    wrapper.dataset.ref = nextRef;
    refreshStepOptions();
    const handledByPendingStep = tryFulfilPendingConfigAssignment(wrapper);
    if (!handledByPendingStep) {
      updateSummary();
    }
    applyTypeValidation();
  };

  typeInput.addEventListener("input", handleTypeChange);
  typeInput.addEventListener("change", handleTypeChange);

  if (configTypeOptions.length === 0) {
    applyTypeValidation();
  }

  const nameCol = document.createElement("div");
  nameCol.className = "col-12 col-xl-7";
  const nameLabel = document.createElement("label");
  nameLabel.className = "form-label";
  nameLabel.textContent = translate(
    "template.editor.label_config_name",
    "Name",
  );
  nameLabel.setAttribute("data-i18n", "template.editor.label_config_name");
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.className = "form-control config-name";
  nameInput.value = name;
  nameInput.placeholder = translate(
    "template.editor.placeholder_config_name",
    "Name",
  );
  nameInput.setAttribute(
    "data-i18n-placeholder",
    "template.editor.placeholder_config_name",
  );
  nameInput.addEventListener("input", () => {
    nameInput.classList.remove("is-invalid");
    const previousRef = wrapper.dataset.ref || "";
    const nextRef = buildConfigReference(typeInput.value, nameInput.value);
    if (previousRef && previousRef !== nextRef) {
      replaceConfigReferenceInSteps(previousRef, nextRef);
    }
    wrapper.dataset.ref = nextRef;
    refreshStepOptions();
    const handledByPendingStep = tryFulfilPendingConfigAssignment(wrapper);
    if (!handledByPendingStep) {
      updateSummary();
    }
  });
  nameCol.append(nameLabel, nameInput);

  const dataCol = document.createElement("div");
  dataCol.className = "col-12";
  const dataLabel = document.createElement("label");
  dataLabel.className = "form-label";
  dataLabel.textContent = translate(
    "template.editor.label_config_data",
    "Data",
  );
  dataLabel.setAttribute("data-i18n", "template.editor.label_config_data");

  const supportsAce =
    typeof window !== "undefined" && typeof window.ace !== "undefined";

  const dataWrapper = document.createElement("div");
  dataWrapper.className = "config-data-wrapper";

  const editorContainer = document.createElement("div");
  editorContainer.className =
    "config-data-editor ace-editor border rounded position-relative";
  editorContainer.style.minHeight = "220px";
  editorContainer.style.height = "220px";
  editorContainer.style.width = "100%";

  const dataInput = document.createElement("textarea");
  dataInput.className = supportsAce
    ? "config-data visually-hidden"
    : "form-control config-data";
  dataInput.rows = supportsAce ? 3 : 6;
  dataInput.value = data;
  dataInput.placeholder = translate(
    "template.editor.placeholder_config_data",
    "Data",
  );
  dataInput.setAttribute(
    "data-i18n-placeholder",
    "template.editor.placeholder_config_data",
  );
  dataInput.setAttribute("aria-hidden", supportsAce ? "true" : "false");

  const dataInputId = `${wrapper.dataset.configId}-config-data`;
  dataInput.id = dataInputId;
  dataLabel.setAttribute("for", dataInputId);

  if (supportsAce) {
    dataWrapper.append(editorContainer);
  }
  dataWrapper.append(dataInput);
  dataCol.append(dataLabel, dataWrapper);

  const actionsCol = document.createElement("div");
  actionsCol.className =
    "col-12 d-flex justify-content-lg-end align-items-start";
  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "btn btn-outline-danger btn-sm w-100 w-lg-auto";
  removeBtn.innerHTML = '<i class="bx bx-trash"></i>';
  removeBtn.title = translate("template.editor.button_remove", "Remove");
  removeBtn.setAttribute("data-i18n-title", "template.editor.button_remove");
  removeBtn.addEventListener("click", () => {
    const previousRef = wrapper.dataset.ref || "";
    disposeConfigEditor(wrapper);
    wrapper.remove();
    if (previousRef) {
      replaceConfigReferenceInSteps(previousRef, "");
    }
    refreshStepOptions();
    toggleEmptyState(dom.configsList, dom.configsEmpty);
    updateSummary();
  });
  actionsCol.append(removeBtn);

  row.append(typeCol, nameCol, dataCol, actionsCol);
  body.append(row);
  wrapper.append(body);
  dom.configsList.append(wrapper);
  if (supportsAce) {
    ensureConfigEditor(wrapper, data, typeInput.value);
  }
  wrapper.dataset.ref = buildConfigReference(typeInput.value, nameInput.value);
  toggleEmptyState(dom.configsList, dom.configsEmpty);
  refreshStepOptions();
  updateSummary();
  tryFulfilPendingConfigAssignment(wrapper);
  return wrapper;
};

const reindexSteps = () => {
  const cards = Array.from(dom.stepsList.querySelectorAll(".step-card"));
  const rawPrefix = translate("template.editor.step_prefix", "Step");
  const stepPrefix =
    rawPrefix && rawPrefix !== "undefined" ? rawPrefix : "Step";
  const rawUntitled = translate(
    "template.editor.step_default_title",
    "Untitled step",
  );
  const untitled =
    rawUntitled && rawUntitled !== "undefined" ? rawUntitled : "Untitled step";

  cards.forEach((card, index) => {
    card.dataset.position = index.toString();
    const heading = card.querySelector(".step-heading");
    const titleInput = card.querySelector(".step-title");
    if (heading && titleInput) {
      const title = titleInput.value.trim() || untitled;
      heading.textContent = `${stepPrefix} ${index + 1}: ${title}`;
    }
  });

  cards.forEach((card, index) => {
    const upBtn = card.querySelector(".step-move-up");
    const downBtn = card.querySelector(".step-move-down");
    if (upBtn) upBtn.disabled = index === 0;
    if (downBtn) downBtn.disabled = index === cards.length - 1;
  });

  toggleEmptyState(dom.stepsList, dom.stepsEmpty);
  updateSummary();
};

const moveStep = (card, direction) => {
  if (!card || !dom.stepsList) return;
  if (direction === "up" && card.previousElementSibling) {
    dom.stepsList.insertBefore(card, card.previousElementSibling);
  } else if (direction === "down" && card.nextElementSibling) {
    dom.stepsList.insertBefore(card.nextElementSibling, card);
  }
  reindexSteps();
};

const createStepCard = ({
  title = "",
  subtitle = "",
  settings = [],
  configs = [],
} = {}) => {
  state.stepCounter += 1;
  const wrapper = document.createElement("article");
  wrapper.className = "card shadow-sm border-0 step-card";
  wrapper.dataset.stepId = `step-${state.stepCounter}`;

  const header = document.createElement("div");
  header.className = "card-header bg-transparent border-0 pb-0";

  const headerContent = document.createElement("div");
  headerContent.className =
    "d-flex flex-wrap justify-content-between align-items-center gap-2";

  const heading = document.createElement("h6");
  heading.className = "step-heading mb-0";
  const defaultHeadingLabel = translate(
    "template.editor.step_default_title",
    "Untitled step",
  );
  const sanitizedHeading =
    defaultHeadingLabel && defaultHeadingLabel !== "undefined"
      ? defaultHeadingLabel
      : "Untitled step";
  heading.textContent = title || sanitizedHeading;

  const controls = document.createElement("div");
  controls.className = "btn-group";

  const upBtn = document.createElement("button");
  upBtn.type = "button";
  upBtn.className = "btn btn-outline-secondary btn-sm step-move-up";
  upBtn.innerHTML = '<i class="bx bx-up-arrow-alt"></i>';
  upBtn.title = translate("template.editor.button_move_up", "Move up");
  upBtn.setAttribute("data-i18n-title", "template.editor.button_move_up");
  upBtn.addEventListener("click", () => moveStep(wrapper, "up"));

  const downBtn = document.createElement("button");
  downBtn.type = "button";
  downBtn.className = "btn btn-outline-secondary btn-sm step-move-down";
  downBtn.innerHTML = '<i class="bx bx-down-arrow-alt"></i>';
  downBtn.title = translate("template.editor.button_move_down", "Move down");
  downBtn.setAttribute("data-i18n-title", "template.editor.button_move_down");
  downBtn.addEventListener("click", () => moveStep(wrapper, "down"));

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "btn btn-outline-danger btn-sm";
  removeBtn.innerHTML = '<i class="bx bx-trash"></i>';
  removeBtn.title = translate("template.editor.button_remove", "Remove");
  removeBtn.setAttribute("data-i18n-title", "template.editor.button_remove");
  removeBtn.addEventListener("click", () => {
    showDeleteStepModal(wrapper);
  });

  controls.append(upBtn, downBtn, removeBtn);
  headerContent.append(heading, controls);
  header.append(headerContent);

  const body = document.createElement("div");
  body.className = "card-body pt-3";

  const row = document.createElement("div");
  row.className = "row g-3";

  const titleCol = document.createElement("div");
  titleCol.className = "col-12 col-lg-6 mb-2";
  const titleLabel = document.createElement("label");
  titleLabel.className = "form-label";
  titleLabel.setAttribute("data-i18n", "template.editor.label_step_title");
  titleLabel.textContent = translate(
    "template.editor.label_step_title",
    "Step title",
  );
  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleInput.className = "form-control step-title";
  titleInput.value = title;
  titleInput.placeholder = translate(
    "template.editor.placeholder_step_title",
    "Step title",
  );
  titleInput.setAttribute(
    "data-i18n-placeholder",
    "template.editor.placeholder_step_title",
  );
  titleInput.addEventListener("input", () => {
    reindexSteps();
  });
  titleCol.append(titleLabel, titleInput);

  const subtitleCol = document.createElement("div");
  subtitleCol.className = "col-12 col-lg-6 mb-2";
  const subtitleLabel = document.createElement("label");
  subtitleLabel.className = "form-label";
  subtitleLabel.setAttribute(
    "data-i18n",
    "template.editor.label_step_subtitle",
  );
  subtitleLabel.textContent = translate(
    "template.editor.label_step_subtitle",
    "Step subtitle",
  );
  const subtitleInput = document.createElement("input");
  subtitleInput.type = "text";
  subtitleInput.className = "form-control step-subtitle";
  subtitleInput.value = subtitle || "";
  subtitleInput.placeholder = translate(
    "template.editor.placeholder_step_subtitle",
    "Step subtitle",
  );
  subtitleInput.setAttribute(
    "data-i18n-placeholder",
    "template.editor.placeholder_step_subtitle",
  );
  subtitleCol.append(subtitleLabel, subtitleInput);

  const settingsCol = document.createElement("div");
  settingsCol.className = "col-12 col-lg-6 mt-3 mt-lg-0";
  const settingsLabel = document.createElement("label");
  settingsLabel.className =
    "form-label d-flex justify-content-between align-items-center";
  settingsLabel.setAttribute(
    "data-i18n",
    "template.editor.label_step_settings",
  );
  settingsLabel.textContent = translate(
    "template.editor.label_step_settings",
    "Settings in this step",
  );

  const settingsControls = document.createElement("div");
  settingsControls.className = "row g-2 align-items-stretch mb-2";

  const settingsSelect = document.createElement("select");
  settingsSelect.className = "form-select form-select-sm step-settings-select";
  settingsSelect.setAttribute(
    "aria-label",
    translate(
      "template.editor.step_settings_selection_title",
      "Select existing settings",
    ),
  );
  settingsSelect.setAttribute(
    "data-i18n-aria-label",
    "template.editor.step_settings_selection_title",
  );

  const settingsSelectWrapper = document.createElement("div");
  settingsSelectWrapper.className = "col-12 col-md";
  settingsSelectWrapper.append(settingsSelect);

  const addSettingWrapper = document.createElement("div");
  addSettingWrapper.className = "col-12 col-md-auto d-grid";

  const addSettingBtn = document.createElement("button");
  addSettingBtn.type = "button";
  addSettingBtn.className =
    "btn btn-sm btn-outline-primary step-settings-add d-flex align-items-center justify-content-center gap-1 w-100";
  addSettingBtn.disabled = true;
  const addSettingIcon = document.createElement("i");
  addSettingIcon.className = "bx bx-plus";
  addSettingBtn.append(addSettingIcon);

  const handleAddSetting = () => {
    const selectedKey = settingsSelect.value;
    if (!selectedKey) return;
    if (assignSettingToStep(wrapper, selectedKey)) {
      settingsSelect.value = "";
      addSettingBtn.disabled = true;
    }
  };

  addSettingBtn.addEventListener("click", handleAddSetting);
  settingsSelect.addEventListener("change", (event) => {
    const selectedKey = event.target.value;
    addSettingBtn.disabled = !selectedKey;
  });

  addSettingWrapper.append(addSettingBtn);
  settingsControls.append(settingsSelectWrapper, addSettingWrapper);

  const settingsList = document.createElement("div");
  settingsList.className = "list-group step-settings-list";
  settingsList.setAttribute("role", "list");

  settingsCol.append(settingsLabel, settingsControls, settingsList);

  const configsCol = document.createElement("div");
  configsCol.className = "col-12 col-lg-6 mt-3 mt-lg-0";
  const configsLabel = document.createElement("label");
  configsLabel.className =
    "form-label d-flex justify-content-between align-items-center";
  configsLabel.setAttribute("data-i18n", "template.editor.label_step_configs");
  configsLabel.textContent = translate(
    "template.editor.label_step_configs",
    "Configs in this step",
  );

  const configsControls = document.createElement("div");
  configsControls.className = "row g-2 align-items-stretch mb-2";

  const configsSelect = document.createElement("select");
  configsSelect.className = "form-select form-select-sm step-configs-select";
  configsSelect.setAttribute(
    "aria-label",
    translate(
      "template.editor.step_configs_selection_title",
      "Select existing configs",
    ),
  );
  configsSelect.setAttribute(
    "data-i18n-aria-label",
    "template.editor.step_configs_selection_title",
  );

  const configsSelectWrapper = document.createElement("div");
  configsSelectWrapper.className = "col-12 col-md";
  configsSelectWrapper.append(configsSelect);

  const addConfigWrapper = document.createElement("div");
  addConfigWrapper.className = "col-12 col-md-auto d-grid";

  const addConfigBtn = document.createElement("button");
  addConfigBtn.type = "button";
  addConfigBtn.className =
    "btn btn-sm btn-outline-primary step-configs-add d-flex align-items-center justify-content-center gap-1 w-100";
  addConfigBtn.disabled = true;
  const addConfigIcon = document.createElement("i");
  addConfigIcon.className = "bx bx-plus";
  addConfigBtn.append(addConfigIcon);

  const handleAddConfig = () => {
    const selectedRef = configsSelect.value;
    if (!selectedRef) return;
    if (assignConfigToStep(wrapper, selectedRef)) {
      configsSelect.value = "";
      addConfigBtn.disabled = true;
    }
  };

  addConfigBtn.addEventListener("click", handleAddConfig);
  configsSelect.addEventListener("change", (event) => {
    const selectedRef = event.target.value;
    addConfigBtn.disabled = !selectedRef;
  });

  addConfigWrapper.append(addConfigBtn);
  configsControls.append(configsSelectWrapper, addConfigWrapper);

  const configsList = document.createElement("div");
  configsList.className = "list-group step-configs-list";
  configsList.setAttribute("role", "list");

  configsCol.append(configsLabel, configsControls, configsList);

  configureDraggableList(settingsList, { type: "settings" });

  configureDraggableList(configsList, { type: "configs" });

  row.append(titleCol, subtitleCol, settingsCol, configsCol);
  body.append(row);
  wrapper.append(header, body);
  dom.stepsList.append(wrapper);

  (settings || []).forEach((key) =>
    assignSettingToStep(wrapper, key, { skipRefresh: true, skipSummary: true }),
  );
  (configs || []).forEach((ref) =>
    assignConfigToStep(wrapper, ref, { skipRefresh: true, skipSummary: true }),
  );

  updateStepSettingsButtonState(wrapper);
  updateStepConfigsButtonState(wrapper);
  refreshStepOptions();
  reindexSteps();
};

const initialiseCollections = () => {
  const template = ctx.template || {};

  const settingsEntries = Object.entries(template.settings || {});
  if (settingsEntries.length > 0) {
    settingsEntries
      .sort((a, b) => compareSettingKeys(a[0], b[0]))
      .forEach(([key, value]) =>
        createSettingRow({ key, value, catalogEntry: getCatalogEntry(key) }),
      );
    sortSettingRows();
  } else {
    toggleEmptyState(dom.settingsList, dom.settingsEmpty);
  }

  if (Array.isArray(template.configs) && template.configs.length > 0) {
    template.configs.forEach((config) =>
      createConfigRow({
        type: config.type || "",
        name: config.name || "",
        data: config.data || "",
      }),
    );
  } else {
    toggleEmptyState(dom.configsList, dom.configsEmpty);
  }

  if (Array.isArray(template.steps) && template.steps.length > 0) {
    template.steps.forEach((step) =>
      createStepCard({
        title: step.title || "",
        subtitle: step.subtitle || "",
        settings: step.settings || [],
        configs: step.configs || [],
      }),
    );
  } else {
    toggleEmptyState(dom.stepsList, dom.stepsEmpty);
  }

  refreshStepOptions();
  reindexSteps();
  updateSummary();
  refreshSettingSelector({ maintainSelection: false });
};

const collectFormData = () => {
  const errors = [];

  const templateId =
    ctx.mode === "edit"
      ? ctx.templateId
      : (dom.templateIdInput?.value || "").trim();
  if (!templateId) {
    errors.push(
      translate(
        "template.editor.validation_id_required",
        "Template ID is required.",
      ),
    );
  }

  const templateName = (dom.templateNameInput?.value || "").trim();

  const settings = {};
  const seenSettings = new Set();
  dom.settingsList.querySelectorAll(".setting-row").forEach((row) => {
    const keyInput = row.querySelector(".setting-key");
    if (!keyInput) return;
    const key = keyInput.value.trim();
    if (!key) {
      keyInput.classList.add("is-invalid");
      errors.push(
        translate(
          "template.editor.validation_setting_key",
          "Each setting must have a key.",
        ),
      );
      return;
    }
    if (seenSettings.has(key)) {
      keyInput.classList.add("is-invalid");
      errors.push(
        translate(
          "template.editor.validation_settings_unique",
          "Each setting key must be unique.",
        ),
      );
      return;
    }
    seenSettings.add(key);
    const control = row.settingControl;
    const value = control ? getSettingControlValue(control) : "";
    settings[key] = value;
  });

  const configs = [];
  const seenConfigs = new Set();
  const invalidConfigTypeMessage = translate(
    "template.editor.validation_config_type_multisite",
    "Config type must be one of the multisite-compatible types.",
  );
  dom.configsList.querySelectorAll(".config-row").forEach((row) => {
    const typeInput = row.querySelector(".config-type");
    const nameInput = row.querySelector(".config-name");
    const dataInput = row.querySelector(".config-data");

    const rawType = typeInput ? typeInput.value : "";
    const rawName = nameInput ? nameInput.value : "";
    const normalizedType = normalizeConfigType(rawType);
    const normalizedName = normalizeConfigName(rawName);
    const data = dataInput ? dataInput.value : "";
    const reference = buildConfigReference(rawType, rawName);

    if (!normalizedType && !normalizedName && !data) {
      return;
    }

    if (!normalizedType) {
      const message = translate(
        "template.editor.validation_config_type_required",
        "Config type is required when a config is defined.",
      );
      if (typeInput) markConfigTypeInvalid(typeInput, message);
      errors.push(message);
      return;
    }

    if (
      allowedConfigTypeValues.size > 0 &&
      !allowedConfigTypeValues.has(normalizedType)
    ) {
      if (typeInput) {
        markConfigTypeInvalid(typeInput, invalidConfigTypeMessage);
      }
      if (!errors.includes(invalidConfigTypeMessage)) {
        errors.push(invalidConfigTypeMessage);
      }
      return;
    }

    if (!normalizedName) {
      if (nameInput) nameInput.classList.add("is-invalid");
      errors.push(
        translate(
          "template.editor.validation_config_name_required",
          "Config name is required when a config is defined.",
        ),
      );
      return;
    }

    if (seenConfigs.has(reference)) {
      if (nameInput) nameInput.classList.add("is-invalid");
      errors.push(
        translate(
          "template.editor.validation_configs_unique",
          "Each config name must be unique.",
        ),
      );
      return;
    }
    seenConfigs.add(reference);

    const configPayload = { type: normalizedType, name: normalizedName };
    if (data) configPayload.data = data;
    configs.push(configPayload);
  });

  const steps = [];
  dom.stepsList.querySelectorAll(".step-card").forEach((card) => {
    const titleInput = card.querySelector(".step-title");
    const subtitleInput = card.querySelector(".step-subtitle");

    const stepPayload = {
      title: titleInput ? titleInput.value.trim() : "",
      settings: getStepSettings(card),
      configs: getStepConfigs(card),
    };

    const subtitleValue = subtitleInput ? subtitleInput.value.trim() : "";
    if (subtitleValue) {
      stepPayload.subtitle = subtitleValue;
    }

    steps.push(stepPayload);
  });

  return {
    isValid: errors.length === 0,
    errors,
    payload: {
      id: templateId,
      name: templateName || templateId,
      settings,
      steps,
      configs,
    },
  };
};

const submitForm = async (event) => {
  event.preventDefault();
  if (state.isSaving) return;
  clearFeedback();

  const { isValid, errors, payload } = collectFormData();
  if (!isValid) {
    showFeedback("danger", errors);
    return;
  }

  const endpoint =
    ctx.mode === "edit" ? ctx.routes?.update : ctx.routes?.create;
  if (!endpoint) {
    showFeedback(
      "danger",
      translate(
        "template.editor.error_missing_endpoint",
        "Unable to determine submission endpoint.",
      ),
    );
    return;
  }

  const formData = new FormData();
  formData.append("csrf_token", ctx.csrfToken || "");
  formData.append("template", JSON.stringify(payload));

  try {
    setSaving(true);
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
      body: formData,
    });

    const result = await response.json().catch(() => ({}));

    if (!response.ok || result.status !== "success") {
      const message =
        result.message ||
        translate(
          "template.editor.error_generic",
          "Something went wrong. Please try again.",
        );
      showFeedback("danger", message);
      setSaving(false);
      return;
    }

    window.location.href = ctx.routes?.list || "/templates";
  } catch (error) {
    showFeedback(
      "danger",
      translate(
        "template.editor.error_generic",
        "Something went wrong. Please try again.",
      ),
    );
    setSaving(false);
  }
};

const resetValidationStyles = () => {
  dom.settingsList
    .querySelectorAll(".setting-key")
    .forEach((input) => input.classList.remove("is-invalid"));
  dom.configsList.querySelectorAll(".config-type").forEach((input) => {
    delete input.dataset.invalidMessage;
    markConfigTypeValid(input);
    setConfigTypeDisplay(input, input.value);
  });
  dom.configsList
    .querySelectorAll(".config-name")
    .forEach((input) => input.classList.remove("is-invalid"));
};

const initEventListeners = () => {
  if (dom.settingSelectorOpenBtn) {
    dom.settingSelectorOpenBtn.setAttribute("aria-expanded", "false");
    dom.settingSelectorOpenBtn.addEventListener("click", () => {
      openSettingSelector();
    });
  }

  if (dom.settingSelectorPlugin) {
    dom.settingSelectorPlugin.addEventListener("change", (event) => {
      settingSelectorState.plugin = event.target.value || "";
      refreshSettingSelector({ maintainSelection: false });
    });
  }

  if (dom.settingSelectorType) {
    dom.settingSelectorType.addEventListener("change", (event) => {
      settingSelectorState.type = event.target.value || "";
      refreshSettingSelector({ maintainSelection: false });
    });
  }

  if (dom.settingSelectorSearch) {
    dom.settingSelectorSearch.addEventListener("input", (event) => {
      settingSelectorState.query = event.target.value || "";
      refreshSettingSelector({ maintainSelection: false });
    });
    dom.settingSelectorSearch.addEventListener(
      "keydown",
      handleSettingSelectorSearchKeydown,
    );
  }

  if (dom.settingSelectorClear) {
    dom.settingSelectorClear.addEventListener("click", () => {
      if (dom.settingSelectorSearch) {
        dom.settingSelectorSearch.value = "";
        dom.settingSelectorSearch.focus();
      }
      settingSelectorState.query = "";
      refreshSettingSelector({ maintainSelection: false });
    });
  }

  if (dom.settingSelectorApply) {
    dom.settingSelectorApply.addEventListener("click", (event) => {
      const added = commitSelectedSetting({ keepOpen: event.shiftKey });
      if (added && event.shiftKey && dom.settingSelectorSearch) {
        dom.settingSelectorSearch.focus();
        dom.settingSelectorSearch.select();
      } else if (added && dom.settingSelectorOpenBtn) {
        dom.settingSelectorOpenBtn.focus();
      }
    });
  }

  if (dom.settingSelectorModal) {
    dom.settingSelectorModal.addEventListener("shown.bs.modal", () => {
      settingSelectorState.modalOpen = true;
      if (dom.settingSelectorSearch) {
        settingSelectorState.query = dom.settingSelectorSearch.value || "";
        dom.settingSelectorSearch.focus();
        dom.settingSelectorSearch.select();
      }
      if (dom.settingSelectorOpenBtn) {
        dom.settingSelectorOpenBtn.setAttribute("aria-expanded", "true");
      }
      refreshSettingSelector({ maintainSelection: true });
      runTranslations();
    });

    dom.settingSelectorModal.addEventListener("hidden.bs.modal", () => {
      settingSelectorState.modalOpen = false;
      settingSelectorState.selectedKey = null;
      settingSelectorState.query = "";
      if (dom.settingSelectorSearch) dom.settingSelectorSearch.value = "";
      updateSettingSelectorApplyState();
      if (dom.settingSelectorOpenBtn) {
        dom.settingSelectorOpenBtn.focus();
        dom.settingSelectorOpenBtn.setAttribute("aria-expanded", "false");
      }
    });
  }

  if (dom.settingRemoveModal) {
    dom.settingRemoveModal.addEventListener("hidden.bs.modal", () => {
      state.settingToRemove = null;
      if (dom.settingRemoveName) dom.settingRemoveName.textContent = "";
    });
  }

  if (dom.confirmSettingRemoveBtn) {
    dom.confirmSettingRemoveBtn.addEventListener("click", () => {
      if (!state.settingToRemove) return;
      removeSettingRow(state.settingToRemove);
      state.settingToRemove = null;
      closeSettingRemoveModal();
    });
  }

  if (dom.addConfigBtn) {
    dom.addConfigBtn.addEventListener("click", () => {
      createConfigRow();
    });
  }

  if (dom.addStepBtn) {
    dom.addStepBtn.addEventListener("click", () => {
      createStepCard();
    });
  }

  if (dom.form) {
    dom.form.addEventListener("submit", (event) => {
      resetValidationStyles();
      submitForm(event);
    });
  }

  document.querySelectorAll("[data-scroll-target]").forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      smoothScrollTo(trigger.getAttribute("data-scroll-target"));
    });
  });

  // Delete step modal bindings
  if (dom.deleteStepModal) {
    // Confirm deletion
    if (dom.confirmDeleteStepBtn) {
      dom.confirmDeleteStepBtn.addEventListener("click", () => {
        if (!state.stepToDelete) return;
        const wrapper = state.stepToDelete;
        getStepSettings(wrapper).forEach((key) =>
          settingAssignments.delete(key),
        );
        getStepConfigs(wrapper).forEach((ref) => configAssignments.delete(ref));
        wrapper.remove();
        state.stepToDelete = null;
        refreshStepOptions();
        reindexSteps();
        updateSummary();
        if (deleteStepModalInstance) deleteStepModalInstance.hide();
      });
    }

    // Cleanup on modal hide
    dom.deleteStepModal.addEventListener("hidden.bs.modal", () => {
      state.stepToDelete = null;
      if (dom.deleteStepTitle) dom.deleteStepTitle.textContent = "";
      if (dom.deleteStepItems) dom.deleteStepItems.textContent = "";
    });
  }
};

const initTemplateEditor = () => {
  if (!dom.form) return;
  setupThemeSync();
  populateSettingSelectorFilters();
  initialiseCollections();
  refreshConfigEditorThemes();
  initEventListeners();
};

initTemplateEditor();
applyTranslations();
