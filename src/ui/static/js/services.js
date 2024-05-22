import {
  Popover,
  TabsSelect,
  FormatValue,
  FilterSettings,
  CheckNoMatchFilter,
  showInvalid,
  SettingsAdvanced,
} from "./utils/settings.js";

import { Filter, Dropdown } from "./utils/dashboard.js";

class SettingsService {
  constructor() {
    this.prefix = "services";
    this.settingsMultiple = JSON.parse(
      document
        .querySelector("input[data-plugins-multiple]")
        .getAttribute("data-plugins-multiple")
        .replaceAll(`'`, `"`),
    );
    this.advancedSettings = new SettingsAdvanced(
      document.querySelector("[data-advanced][data-services-modal-form]"),
      this.settingsMultiple,
      "services",
    );
    this.isReadOnly =
      document
        .querySelector("[data-services-modal]")
        .getAttribute("data-readonly") === "true";

    this.initSettingsService();
  }

  getActionData(target) {
    const action = target
      .closest("button")
      .getAttribute("data-services-action");
    const serviceName = target
      .closest("button")
      .getAttribute("data-services-name");
    const isDraft =
      target
        .closest("[data-services-service]")
        .querySelector("[data-is-draft]")
        .getAttribute("data-value") || "no";

    const method =
      target
        .closest("[data-services-service]")
        .querySelector("[data-service-method]")
        .getAttribute("data-value") || "no";

    const oldServName =
      target
        .closest("[data-services-service]")
        .querySelector("[data-old-name]")
        .getAttribute("data-value") || "";

    this.currMethod = method;

    const operation = action === "clone" || action === "new" ? "new" : action;

    const settings = JSON.parse(
      target.closest("[data-settings]").getAttribute("data-settings"),
    );

    return [
      action,
      serviceName,
      oldServName,
      isDraft,
      method,
      settings,
      operation,
    ];
  }

  initSettingsService() {
    window.addEventListener("click", (e) => {
      //edit / clone action
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-action`) === "edit" ||
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-action`) === "clone" ||
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-action`) === "new"
        ) {
          const [
            action,
            serviceName,
            oldServName,
            isDraft,
            method,
            settings,
            operation,
          ] = this.getActionData(e.target);

          const forceDisabled = this.isReadOnly ? true : false;
          const forceEnabled = action === "new" ? true : false;
          const setMethodUI =
            action === "new" || action === "clone" ? true : false;
          const emptyServerName =
            action === "new" || action === "clone" ? true : false;

          this.advancedSettings.setAdvanced(
            action,
            oldServName,
            operation,
            settings,
            setMethodUI,
            forceEnabled,
            emptyServerName,
            forceDisabled,
          );
        }
      } catch (err) {}
    });
  }
}

class ServiceModal {
  constructor() {
    //modal elements
    this.modal = document.querySelector("[data-services-modal]");
    this.isReadOnly =
      document
        .querySelector("[data-services-modal]")
        .getAttribute("data-readonly") === "true";
    this.modalTitle = this.modal.querySelector("[data-services-modal-title]");
    this.modalTabs = this.modal.querySelector(["[data-services-tabs-select]"]);
    this.modalTabsHeader = this.modal.querySelector([
      "[data-services-tabs-select-header]",
    ]);
    this.modalCard = this.modal.querySelector("[data-services-modal-card]");
    //modal forms
    this.formNewEdit = this.modal.querySelector(
      "[data-advanced][data-services-modal-form]",
    );
    this.formDelete = this.modal.querySelector(
      "[data-services-modal-form-delete]",
    );

    //container
    this.container = document.querySelector("main");
    this.currAction = "";
    this.currMethod = "";

    this.init();
  }

  init() {
    this.modal.addEventListener("click", (e) => {
      //close
      try {
        if (
          e.target.closest("button").hasAttribute("data-services-modal-close")
        ) {
          this.closeModal();
        }
      } catch (err) {}
      // switch draft
      try {
        if (e.target.closest("button").hasAttribute("data-toggle-draft-btn")) {
          const draftBtn = e.target.closest("button");
          // check if hidden or not
          const isDraft = draftBtn
            .querySelector("[data-toggle-draft='true']")
            .classList.contains("hidden");
          this.setIsDraft(isDraft ? true : false, "default");
        }
      } catch (err) {}
    });

    this.container.addEventListener("click", (e) => {
      //edit action
      try {
        if (
          e.target.closest("button").getAttribute("data-services-action") ===
            "edit" ||
          e.target.closest("button").getAttribute("data-services-action") ===
            "delete" ||
          e.target.closest("button").getAttribute("data-services-action") ===
            "clone" ||
          e.target.closest("button").getAttribute("data-services-action") ===
            "new"
        ) {
          //set form info and right form
          this.setFormModal(e.target);
        }
      } catch (err) {}
    });
  }

  //store default config data on DOM
  //to update modal data on new button click

  getActionData(target) {
    const action = target
      .closest("button")
      .getAttribute("data-services-action");
    const serviceName = target
      .closest("button")
      .getAttribute("data-services-name");
    const isDraft =
      target
        .closest("[data-services-service]")
        .querySelector("[data-is-draft]")
        .getAttribute("data-value") || "no";

    const method =
      target
        .closest("[data-services-service]")
        .querySelector("[data-service-method]")
        .getAttribute("data-value") || "no";

    let oldServName = "";

    if (action !== "new")
      oldServName =
        target
          .closest("[data-services-service]")
          .querySelector("[data-old-name]")
          .getAttribute("data-value") || "";
    this.currMethod = method;

    return [action, serviceName, oldServName, isDraft, method];
  }

  setFormModal(target) {
    const [action, serviceName, oldServName, isDraft, method] =
      this.getActionData(target);
    this.currAction = action;
    // truncate serviceName if more than 15 characters
    const servName =
      serviceName.length > 15 ? `${serviceName.slice(0, 15)}...` : serviceName;
    this.modalTitle.textContent = `${action} ${servName}`;

    // show / hide components
    this.hideForms();
    this.setCardViewportHeight(action === "delete" ? false : true);
    this.setHeaderActionsVisible(action === "delete" ? false : true);
    this.SetSelectTabsVisible(action === "delete" ? false : true);
    if (action === "edit" || action === "new" || action === "clone") {
      this.resetFilterSettings();
      this.formNewEdit.classList.remove("hidden");

      const oldNameValue = action === "edit" ? oldServName : "";

      const oldNameInps = this.modal.querySelectorAll(
        'input[name="OLD_SERVER_NAME"]',
      );
      oldNameInps.forEach((inp) => {
        inp.setAttribute("value", oldNameValue);
        inp.value = oldNameValue;
      });
    }

    if (action === "delete") {
      this.formDelete.classList.remove("hidden");
      this.formDelete.querySelector(`[data-services-modal-text]`).textContent =
        `Are you sure you want to delete ${serviceName} ?`;
      const nameInp = this.formDelete.querySelector(
        `input[name="SERVER_NAME"]`,
      );
      nameInp.setAttribute("value", serviceName);
      nameInp.value = serviceName;
    }

    this.setIsDraft(isDraft === "yes" ? true : false, method);
    setTimeout(() => {
      this.setActionBtns();
      this.openModal();
    }, 50);
  }

  resetFilterSettings() {
    // Reset select
    const selectTypeAll = document
      .querySelector("#filter-type[data-services-setting-select-dropdown]")
      .querySelector(
        'button[value="all"][data-services-setting-select-dropdown-btn="type"]',
      );
    selectTypeAll.click();
    const inpKeyword = this.modal.querySelector("input#settings-filter");
    inpKeyword.value = "";
    // dispatch event input
    inpKeyword.dispatchEvent(new Event("input"));
  }

  setActionBtns() {
    if (this.isReadOnly) {
      this.modal.querySelectorAll("button[type='submit']").forEach((btn) => {
        btn.setAttribute("disabled", "true");
      });
    }

    if (!this.isReadOnly) {
      this.modal.querySelectorAll("button[type='submit']").forEach((btn) => {
        btn.removeAttribute("disabled");
      });
    }
  }

  setIsDraft(isDraft, method) {
    const draftVal = isDraft ? "yes" : "no";

    const draftInps = this.container.querySelectorAll('input[name="is_draft"]');

    draftInps.forEach((inp) => {
      inp.setAttribute("value", draftVal);
      inp.value = draftVal;
    });

    //Update draft button
    const btn = this.container.querySelector("button[data-toggle-draft-btn]");

    if (
      (!["ui", "default"].includes(method) && this.currAction !== "clone") ||
      this.currAction === "delete"
    ) {
      return btn.classList.add("hidden");
    }

    btn.classList.remove("hidden");

    const showEl = isDraft ? "true" : "false";
    btn.querySelectorAll("[data-toggle-draft]").forEach((item) => {
      if (item.getAttribute("data-toggle-draft") === showEl)
        item.classList.remove("hidden");
      if (item.getAttribute("data-toggle-draft") !== showEl)
        item.classList.add("hidden");
    });
  }

  setHeaderActionsVisible(setVisible) {
    if (setVisible) {
      this.modal
        .querySelector("[data-toggle-draft-btn]")
        .classList.remove("hidden");
    }

    if (!setVisible) {
      this.modal
        .querySelector("[data-toggle-draft-btn]")
        .classList.add("hidden");
    }
  }

  setCardViewportHeight(setAsViewport) {
    if (setAsViewport) {
      this.modalCard.classList.add("h-[90vh]");
      this.modalCard.classList.add("w-full");
    }

    if (!setAsViewport) {
      this.modalCard.classList.remove("h-[90vh]");
      this.modalCard.classList.remove("w-full");
    }
  }

  hideForms() {
    this.formNewEdit.classList.add("hidden");
    this.formDelete.classList.add("hidden");
  }

  SetSelectTabsVisible(setVisible) {
    if (setVisible) {
      this.modalTabs.classList.add("grid");
      this.modalTabs.classList.remove("hidden");
      this.modalTabsHeader.classList.add("flex");
      this.modalTabsHeader.classList.remove("hidden");
    }

    if (!setVisible) {
      this.modalTabs.classList.remove("grid");
      this.modalTabs.classList.add("hidden");

      this.modalTabsHeader.classList.remove("flex");
      this.modalTabsHeader.classList.add("hidden");
    }
  }

  closeModal() {
    this.modal.classList.add("hidden");
    this.modal.classList.remove("flex");
  }

  openModal() {
    try {
      //switch to first setting
      document.querySelector("button[data-tab-select-handler]").click();
    } catch (e) {}
    setTimeout(() => {
      this.modal.classList.add("flex");
      this.modal.classList.remove("hidden");
    }, 20);
  }
}

const setDropdown = new Dropdown("services");
const setTabsSelect = new TabsSelect(
  document.querySelector("[data-services-tabs-select]"),
  document.querySelector("[data-advanced][data-services-modal-form]"),
);

const setPopover = new Popover();
const setModal = new ServiceModal();
const format = new FormatValue();
const invalid = new showInvalid();
const setFilterGlobal = new FilterSettings(
  "settings-filter",
  document.querySelector("[data-services-tabs-select]"),
  document.querySelector("[data-advanced][data-services-modal-form]"),
  "services",
);

const settings = new SettingsService();

const checkServiceModalKeyword = new CheckNoMatchFilter(
  document.querySelector("input#settings-filter"),
  "input",
  document
    .querySelector("[data-services-modal-form]")
    .querySelectorAll("[data-plugin-item]"),
  document.querySelector("[data-services-modal-form]"),
  document.querySelector("[data-advanced][data-services-nomatch]"),
);

const checkServiceModalSelect = new CheckNoMatchFilter(
  document.querySelectorAll(
    "button[data-services-setting-select-dropdown-btn]",
  ),
  "select",
  document
    .querySelector("[data-services-modal-form]")
    .querySelectorAll("[data-plugin-item]"),
  document.querySelector("[data-services-modal-form]"),
  document.querySelector("[data-advanced][data-services-nomatch]"),
);

const filterContainer = document.querySelector(`[data-services-filter]`);
if (filterContainer) {
  const noMatchEl = document.querySelector("[data-services-nomatch-card]");
  const filterEls = document.querySelectorAll(`[data-services-card]`);
  const keywordFilter = {
    handler: document.querySelector("input#service-name-keyword"),
    handlerType: "input",
    value: document.querySelector("input#service-name-keyword").value,
    filterEls: filterEls,
    filterAtt: "data-services-name",
    filterType: "keyword",
  };
  const methodFilter = {
    handler: document.querySelector(
      "[data-services-setting-select-dropdown='method']",
    ),
    handlerType: "select",
    value: document
      .querySelector("[data-services-setting-select-text='method']")
      .textContent.trim()
      .toLowerCase(),
    filterEls: filterEls,
    filterAtt: "data-services-method",
    filterType: "match",
  };
  const stateFilter = {
    handler: document.querySelector(
      "[data-services-setting-select-dropdown='state']",
    ),
    handlerType: "select",
    value: document
      .querySelector("[data-services-setting-select-text='state']")
      .textContent.trim()
      .toLowerCase(),
    filterEls: filterEls,
    filterAtt: "data-services-state",
    filterType: "match",
  };
  new Filter(
    "services",
    [keywordFilter, methodFilter, stateFilter],
    null,
    noMatchEl,
  );
}
