import {
  Popover,
  TabsSelect,
  FormatValue,
  FilterSettings,
  CheckNoMatchFilter,
  showInvalid,
  SettingsAdvanced,
  SettingsSimple,
  SettingsSwitch,
} from "./utils/settings.js";

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
    this.simpleSettings = new SettingsSimple(
      document.querySelector("[data-simple][data-services-modal-form]"),
      this.settingsMultiple,
      "services",
    );

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
          );

          // Click on right security level dropdown btn
          // This will fire security level event listener
          this.simpleSettings.updateData(
            action,
            oldServName,
            operation,
            settings,
            forceEnabled,
            setMethodUI,
            emptyServerName,
          );
          if (action === "new") {
            document
              .querySelector(
                `button[data-setting-select-dropdown-btn="security-level"][value="standard"]`,
              )
              .click();
            document
              .querySelector(
                `button[data-setting-select-dropdown-btn="security-level"][value="custom"]`,
              )
              .setAttribute("disabled", "true");
          } else {
            document
              .querySelector(
                `button[data-setting-select-dropdown-btn="security-level"][value="custom"]`,
              )
              .click();
            document
              .querySelector(
                `button[data-setting-select-dropdown-btn="security-level"][value="custom"]`,
              )
              .removeAttribute("disabled");
          }
        }
      } catch (err) {
        console.log(err);
      }
      // security level
      try {
        if (
          e.target
            .closest("button")
            .getAttribute("data-setting-select-dropdown-btn") ==
          "security-level"
        ) {
          // get current common values
          const action = this.simpleSettings.currAction;
          const oldServName = this.simpleSettings.oldServName;
          const operation = this.simpleSettings.operation;
          const forceEnabled = this.simpleSettings.forceEnabled;
          const setMethodUI = this.simpleSettings.setMethodUI;
          const emptyServerName = this.simpleSettings.emptyServerName;
          // get custom security level settings of service if custom choose
          const value = e.target.closest("button").getAttribute("value");

          // mainSettings is the settings of the service
          let mainSettings;

          // Try to get settings in a valid format
          try {
            mainSettings = JSON.parse(
              document
                .querySelector(`[data-old-name][data-value="${oldServName}"]`)
                .closest("[data-services-service]")
                .getAttribute("data-settings"),
            );
          } catch (err) {}

          try {
            if (!settings) {
              mainSettings = JSON.parse(
                document
                  .querySelector(`[data-old-name][data-value="${oldServName}"]`)
                  .closest("[data-services-service]")
                  .getAttribute("data-settings")
                  .replaceAll(`'`, `"`),
              );
            }
          } catch (err) {}

          // In case we want a security level, we need to get the settings of the security level
          // In order to filter and merge both to avoid overriding disabled settings (method != ui|default)
          let compareSettings = null;
          if (value !== "custom") {
            // Try to get settings in a valid format
            try {
              compareSettings = JSON.parse(
                document
                  .querySelector(`input#security-level-${value}`)
                  .getAttribute("data-settings"),
              );
            } catch (err) {}

            try {
              if (!compareSettings) {
                compareSettings = JSON.parse(
                  document
                    .querySelector(`input#security-level-${value}`)
                    .getAttribute("data-settings")
                    .replaceAll(`'`, `"`),
                );
              }
            } catch (err) {}
          }

          console.log("mainSettings", mainSettings);
          console.log("compareSettings", compareSettings);

          this.simpleSettings.setSimple(
            action,
            oldServName,
            operation,
            mainSettings,
            compareSettings,
            setMethodUI,
            forceEnabled,
            emptyServerName,
            true,
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
    this.modalTitle = this.modal.querySelector("[data-services-modal-title]");
    this.modalTabs = this.modal.querySelector(["[data-services-tabs-select]"]);
    this.modalTabsHeader = this.modal.querySelector([
      "[data-services-tabs-select-header]",
    ]);
    this.modalCard = this.modal.querySelector("[data-services-modal-card]");
    this.switchModeBtn = this.modal.querySelector(
      "[data-toggle-settings-mode-btn]",
    );
    //modal forms
    this.formNewEdit = this.modal.querySelector(
      "[data-advanced][data-services-modal-form]",
    );
    this.formDelete = this.modal.querySelector(
      "[data-services-modal-form-delete]",
    );
    this.simpleForm = this.modal.querySelector(
      "[data-simple][data-services-modal-form]",
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
      } catch (err) {
        console.log(err);
      }
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
    this.modalTitle.textContent = `${action} ${serviceName}`;

    // show / hide components
    this.hideForms();
    this.setCardViewportHeight(action === "delete" ? false : true);
    this.setHeaderActionsVisible(action === "delete" ? false : true);
    this.SetSelectTabsVisible(action === "delete" ? false : true);
    this.setModeVisible(action);
    if (action === "edit" || action === "new" || action === "clone") {
      this.formNewEdit.classList.remove("hidden");
      this.simpleForm.classList.remove("hidden");

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
    this.openModal();
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
      this.modal
        .querySelector("[data-toggle-settings-mode-btn]")
        .classList.remove("hidden");
    }

    if (!setVisible) {
      this.modal
        .querySelector("[data-toggle-draft-btn]")
        .classList.add("hidden");
      this.modal
        .querySelector("[data-toggle-settings-mode-btn]")
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

  switchMode(mode) {
    if (mode === "advanced") {
      this.formNewEdit.classList.remove("hidden");
      this.simpleForm.classList.add("hidden");
    }

    if (mode === "simple") {
      this.formNewEdit.classList.add("hidden");
      this.simpleForm.classList.remove("hidden");
    }
  }

  setModeVisible(action) {
    if (action === "new" || action === "clone" || action === "edit") {
      this.switchModeBtn.classList.remove("hidden");
    } else {
      this.switchModeBtn.classList.add("hidden");
    }
  }

  hideForms() {
    this.formNewEdit.classList.add("hidden");
    this.simpleForm.classList.add("hidden");
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

class Dropdown {
  constructor(prefix = "services") {
    this.prefix = prefix;
    this.container = document.querySelector("main");
    this.lastDrop = "";
    this.initDropdown();
  }

  initDropdown() {
    this.container.addEventListener("click", (e) => {
      //SELECT BTN LOGIC
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`data-${this.prefix}-setting-select`) &&
          !e.target.closest("button").hasAttribute(`disabled`)
        ) {
          const btnName = e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select`);
          if (this.lastDrop !== btnName) {
            this.lastDrop = btnName;
            this.closeAllDrop();
          }

          this.toggleSelectBtn(e);
        }
      } catch (err) {}
      //SELECT DROPDOWN BTN LOGIC
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`data-${this.prefix}-setting-select-dropdown-btn`)
        ) {
          const btn = e.target.closest("button");
          const btnValue = btn.getAttribute("value");
          const btnSetting = btn.getAttribute(
            `data-${this.prefix}-setting-select-dropdown-btn`,
          );
          //stop if same value to avoid new fetching
          const isSameVal = this.isSameValue(btnSetting, btnValue);
          if (isSameVal) return this.hideDropdown(btnSetting);
          //else, add new value to custom
          this.setSelectNewValue(btnSetting, btnValue);
          //close dropdown and change style
          this.hideDropdown(btnSetting);

          if (
            !e.target.closest("button").hasAttribute(`data-${this.prefix}-file`)
          ) {
            this.changeDropBtnStyle(btnSetting, btn);
          }
          //show / hide filter
          if (btnSetting === "instances") {
            this.hideFilterOnLocal(btn.getAttribute("data-_type"));
          }
        }
      } catch (err) {}
    });
  }

  closeAllDrop() {
    const drops = document.querySelectorAll(
      `[data-${this.prefix}-setting-select-dropdown]`,
    );
    drops.forEach((drop) => {
      drop.classList.add("hidden");
      drop.classList.remove("flex");
      document
        .querySelector(
          `svg[data-${this.prefix}-setting-select="${drop.getAttribute(
            `data-${this.prefix}-setting-select-dropdown`,
          )}"]`,
        )
        .classList.remove("rotate-180");
    });
  }

  isSameValue(btnSetting, value) {
    const selectCustom = document.querySelector(
      `[data-${this.prefix}-setting-select-text="${btnSetting}"]`,
    );
    const currVal = selectCustom.textContent;
    return currVal === value ? true : false;
  }

  setSelectNewValue(btnSetting, value) {
    const selectCustom = document.querySelector(
      `[data-${this.prefix}-setting-select="${btnSetting}"]`,
    );
    selectCustom.querySelector(
      `[data-${this.prefix}-setting-select-text]`,
    ).textContent = value;
  }

  hideDropdown(btnSetting) {
    //hide dropdown
    const dropdownEl = document.querySelector(
      `[data-${this.prefix}-setting-select-dropdown="${btnSetting}"]`,
    );
    dropdownEl.classList.add("hidden");
    dropdownEl.classList.remove("flex");
    //svg effect
    const dropdownChevron = document.querySelector(
      `svg[data-${this.prefix}-setting-select="${btnSetting}"]`,
    );
    dropdownChevron.classList.remove("rotate-180");
  }

  changeDropBtnStyle(btnSetting, selectedBtn) {
    const dropdownEl = document.querySelector(
      `[data-${this.prefix}-setting-select-dropdown="${btnSetting}"]`,
    );
    //reset dropdown btns
    const btnEls = dropdownEl.querySelectorAll("button");

    btnEls.forEach((btn) => {
      btn.classList.remove(
        "bg-primary",
        "dark:bg-primary",
        "text-gray-300",
        "text-gray-300",
      );
      btn.classList.add("bg-white", "dark:bg-slate-700", "text-gray-700");
    });
    //highlight clicked btn
    selectedBtn.classList.remove(
      "bg-white",
      "dark:bg-slate-700",
      "text-gray-700",
    );
    selectedBtn.classList.add("dark:bg-primary", "bg-primary", "text-gray-300");
  }

  toggleSelectBtn(e) {
    const attribute = e.target
      .closest("button")
      .getAttribute(`data-${this.prefix}-setting-select`);
    //toggle dropdown
    const dropdownEl = document.querySelector(
      `[data-${this.prefix}-setting-select-dropdown="${attribute}"]`,
    );
    const dropdownChevron = document.querySelector(
      `svg[data-${this.prefix}-setting-select="${attribute}"]`,
    );
    dropdownEl.classList.toggle("hidden");
    dropdownEl.classList.toggle("flex");
    dropdownChevron.classList.toggle("rotate-180");
  }

  //hide date filter on local
  hideFilterOnLocal(type) {
    if (type === "local") {
      this.hideInp(`input#from-date`);
      this.hideInp(`input#to-date`);
    }

    if (type !== "local") {
      this.showInp(`input#from-date`);
      this.showInp(`input#to-date`);
    }
  }

  showInp(selector) {
    document.querySelector(selector).closest("div").classList.add("flex");
    document.querySelector(selector).closest("div").classList.remove("hidden");
  }

  hideInp(selector) {
    document.querySelector(selector).closest("div").classList.add("hidden");
    document.querySelector(selector).closest("div").classList.remove("flex");
  }
}

class Filter {
  constructor(prefix = "services") {
    this.prefix = prefix;
    this.container =
      document.querySelector(`[data-${this.prefix}-filter]`) || null;
    this.keyInp = document.querySelector("input#service-name-keyword");
    this.stateValue = "all";
    this.methodValue = "all";
    this.initHandler();
  }

  initHandler() {
    if (!this.container) return;
    //STATE HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
          "state"
        ) {
          setTimeout(() => {
            const value = document
              .querySelector(
                `[data-${this.prefix}-setting-select-text="state"]`,
              )
              .textContent.trim()
              .toLowerCase();

            this.stateValue = value;
            //run filter
            this.filter();
          }, 10);
        }
      } catch (err) {}
    });
    //METHOD HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
          "method"
        ) {
          setTimeout(() => {
            const value = document
              .querySelector(
                `[data-${this.prefix}-setting-select-text="method"]`,
              )
              .textContent.trim()
              .toLowerCase();

            this.methodValue = value;
            //run filter
            this.filter();
          }, 10);
        }
      } catch (err) {}
    });
    //KEYWORD HANDLER
    this.keyInp.addEventListener("input", (e) => {
      this.filter();
    });
  }

  filter() {
    const services = document.querySelectorAll(`[data-${this.prefix}-card]`);
    if (services.length === 0) return;
    //reset
    for (let i = 0; i < services.length; i++) {
      const el = services[i];
      el.classList.remove("hidden");
    }
    //filter type
    this.setFilterState(services);
    this.setFilterMethod(services);
    this.setFilterKeyword(services);
  }

  setFilterState(services) {
    if (this.stateValue === "all") return;
    for (let i = 0; i < services.length; i++) {
      const el = services[i];
      const type = el
        .querySelector(`[data-${this.prefix}-state]`)
        .getAttribute(`data-${this.prefix}-state`)
        .trim()
        .toLowerCase();
      if (type !== this.stateValue) el.classList.add("hidden");
    }
  }

  setFilterMethod(services) {
    if (this.methodValue === "all") return;
    for (let i = 0; i < services.length; i++) {
      const el = services[i];
      const type = el
        .querySelector(`[data-${this.prefix}-method]`)
        .getAttribute(`data-${this.prefix}-method`)
        .trim()
        .toLowerCase();
      if (type !== this.methodValue) el.classList.add("hidden");
    }
  }

  setFilterKeyword(jobs) {
    const keyword = this.keyInp.value.trim().toLowerCase();
    if (!keyword) return;
    for (let i = 0; i < jobs.length; i++) {
      const el = jobs[i];
      const name = el
        .querySelector(`[data-${this.prefix}-name]`)
        .textContent.trim()
        .toLowerCase();

      if (!name.includes(keyword)) el.classList.add("hidden");
    }
  }
}

const setDropdown = new Dropdown();
const setFilter = new Filter();
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

const switchSettings = new SettingsSwitch(
  document.querySelector("[data-toggle-settings-mode-btn]"),
  document.querySelector("main"),
  ["advanced", "simple"],
  "services",
);

const checkServiceModalKeyword = new CheckNoMatchFilter(
  document.querySelector("input#settings-filter"),
  "input",
  document
    .querySelector("[data-services-modal-form]")
    .querySelectorAll("[data-plugin-item]"),
  document.querySelector("[data-services-modal-form]"),
  document.querySelector("[data-services-nomatch]"),
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
  document.querySelector("[data-services-nomatch]"),
);

try {
  const checkServiceCardKeyword = new CheckNoMatchFilter(
    document.querySelectorAll("input#service-name-keyword"),
    "input",
    document.querySelectorAll("[data-services-card]"),
    false,
    document.querySelector("[data-services-nomatch-card]"),
  );

  const checkServiceCardSelect = new CheckNoMatchFilter(
    document.querySelectorAll(
      "button[data-services-setting-select-dropdown-btn]",
    ),
    "select",
    document.querySelectorAll("[data-services-card]"),
    false,
    document.querySelector("[data-services-nomatch-card]"),
  );
} catch (e) {}
