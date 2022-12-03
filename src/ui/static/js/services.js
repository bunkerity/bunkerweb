import { Checkbox, Select } from "./utils/form.js";
import { Popover, Tabs, FormatValue } from "./utils/settings.js";

class ServiceModal {
  constructor() {
    //modal elements
    this.modal = document.querySelector("[services-modal]");
    this.modalTitle = this.modal.querySelector("[services-modal-title]");
    this.modalTabs = this.modal.querySelector(["[services-tabs]"]);
    this.modalTabsHeader = this.modal.querySelector(["[services-tabs-header]"]);

    this.modalCard = this.modal.querySelector("[services-modal-card]");
    //modal forms
    this.formNewEdit = this.modal.querySelector("[services-modal-form]");
    this.formDelete = this.modal.querySelector("[services-modal-form-delete]");
    //container
    this.container = document.querySelector("main");
    //general inputs
    this.inputs = this.modal.querySelectorAll("input[default-value]");
    this.selects = this.modal.querySelectorAll("select[default-value]");
    this.lastGroup = "";
    this.lastAction = "";

    this.init();
  }

  //store default config data on DOM
  //to update modal data on new button click

  init() {
    this.modal.addEventListener("click", (e) => {
      //close
      try {
        if (e.target.closest("button").hasAttribute("services-modal-close")) {
          this.closeModal();
        }
      } catch (err) {}
    });

    this.container.addEventListener("click", (e) => {
      //actions
      try {
        if (e.target.closest("button").hasAttribute("services-action")) {
          //do nothing if same btn and service as before
          const isLastSame = this.isLastServAndAct(e.target);
          if (isLastSame) return;
          //else set the good form
          const action = e.target
            .closest("button")
            .getAttribute("services-action");
          const serviceName = e.target
            .closest("button")
            .getAttribute("services-name");

          let form;
          if (action === "edit" || action === "new") form = this.formNewEdit;
          if (action === "delete") form = this.formDelete;
          this.setForm(action, serviceName, form);
          //reset settings value
          if (action === "edit" || action === "new") this.setDefaultValue();
          //get custom settings of service and apply it to modal settings
          if (action === "edit") {
            const servicesSettings = e.target
              .closest("[services-service]")
              .querySelector("[services-settings]")
              .getAttribute("value");
            const obj = JSON.parse(servicesSettings);
            this.updateModalData(obj);
          }
          //open modal when all done
          this.openModal();
        }
      } catch (err) {}
    });
  }

  isLastServAndAct(target) {
    const serviceName = target.closest("button").getAttribute("services-name");
    const serviceAction = target
      .closest("button")
      .getAttribute("services-action");

    if (this.lastGroup === serviceName && this.lastAction === serviceAction) {
      this.openModal();
      return true;
    } else {
      this.lastGroup = serviceName;
      this.lastAction = serviceAction;
      return false;
    }
  }

  setDefaultValue() {
    this.inputs.forEach((inpt) => {
      const defaultVal = inpt.getAttribute("default-value");
      const defaultMethod = inpt.getAttribute("default-method");
      //SET METHOD
      this.setDisabled(inpt, defaultMethod);

      //SET VALUE
      if (inpt.getAttribute("type") === "checkbox") {
        inpt.checked = defaultVal === "yes" ? true : false;
        inpt.setAttribute("value", defaultVal);
      }

      if (inpt.getAttribute("type") !== "checkbox") {
        inpt.setAttribute("value", defaultVal);
      }
    });

    this.selects.forEach((select) => {
      const defaultVal = select.getAttribute("default-value");
      const defaultMethod = select.getAttribute("default-method");
      if (defaultMethod === "ui" || defaultMethod === "default") {
        document
          .querySelector(
            `[services-setting-select=${select.getAttribute(
              "services-setting-select-default"
            )}]`
          )
          .removeAttribute("disabled");
      } else {
        document
          .querySelector(
            `[services-setting-select=${select.getAttribute(
              "services-setting-select-default"
            )}]`
          )
          .setAttribute("disabled", "");
      }
      select.parentElement
        .querySelector(
          `button[services-setting-select-dropdown-btn][value='${defaultVal}']`
        )
        .click();
    });
    //server name always enabled for default
    this.setNameSetting("ui", "");
  }

  setNameSetting(method, value) {
    const nameInp = document.querySelector('input[name="SERVER_NAME"]');

    if (method === "ui" || method === "default") {
      nameInp.removeAttribute("disabled");
    } else {
      nameInp.setAttribute("disabled", "");
    }

    nameInp.value = value;
  }

  setDisabled(inp, method) {
    if (method === "ui" || method === "default") {
      inp.removeAttribute("disabled");
    } else {
      inp.setAttribute("disabled", "");
    }
  }

  setForm(action, serviceName, formEl) {
    this.modalTitle.textContent = `${action} ${serviceName}`;
    formEl.setAttribute("id", `form-${action}-${serviceName}`);
    formEl
      .querySelector(`input[name="operation"]`)
      .setAttribute("value", action);

    if (action === "edit" || action === "new") {
      this.showNewEditForm();
      formEl
        .querySelector(`input[name="OLD_SERVER_NAME"]`)
        .setAttribute("value", serviceName);
    }

    if (action === "delete") {
      this.showDeleteForm();
      formEl.setAttribute("id", `form-${action}-${serviceName}`);
      formEl
        .querySelector(`input[name="SERVER_NAME"]`)
        .setAttribute("value", serviceName);
      formEl.querySelector(
        `[services-modal-text]`
      ).textContent = `Are you sure you want to delete ${serviceName} ?`;
    }
  }

  showNewEditForm() {
    this.cardViewport();
    this.showTabs();
    this.hideForms();
    this.formNewEdit.classList.remove("hidden");
  }

  showDeleteForm() {
    this.cardNoViewport();
    this.hideTabs();
    this.hideForms();

    this.formDelete.classList.remove("hidden");
  }

  cardViewport() {
    this.modalCard.classList.add("h-[90vh]");
    this.modalCard.classList.add("w-full");
  }

  cardNoViewport() {
    this.modalCard.classList.remove("h-[90vh]");
    this.modalCard.classList.remove("w-full");
  }

  hideForms() {
    this.formNewEdit.classList.add("hidden");
    this.formDelete.classList.add("hidden");
  }

  hideTabs() {
    this.modalTabs.classList.remove("grid");
    this.modalTabs.classList.add("hidden");

    this.modalTabsHeader.classList.remove("flex");
    this.modalTabsHeader.classList.add("hidden");
  }

  showTabs() {
    this.modalTabs.classList.add("grid");
    this.modalTabs.classList.remove("hidden");
    this.modalTabsHeader.classList.add("flex");
    this.modalTabsHeader.classList.remove("hidden");
  }

  updateModalData(settings) {
    //use this to select inputEl and change value
    for (const [key, data] of Object.entries(settings)) {
      //change format to match id
      const value = data["value"];
      const method = data["method"];
      try {
        const inpt = this.modal.querySelector(`[id='${key}']`);
        //SET DISABLED / ENABLED
        this.setDisabled(inpt, method);
        //SET VALUE
        //for regular input
        if (
          inpt.tagName === "INPUT" &&
          inpt.getAttribute("type") !== "checkbox"
        ) {
          inpt.setAttribute("value", value);
        }
        //for checkbox
        if (
          inpt.tagName === "INPUT" &&
          inpt.getAttribute("type") === "checkbox"
        ) {
          inpt.checked = value === "yes" ? true : false;
          inpt.setAttribute("value", value);
        }
        //for select
        if (inpt.tagName === "SELECT") {
          inpt.parentElement
            .querySelector(
              `button[services-setting-select-dropdown-btn][value='${value}']`
            )
            .click();
        }
      } catch (err) {}
    }
    //name setting value
    this.setNameSetting(
      settings["SERVER_NAME"]["method"],
      settings["SERVER_NAME"]["value"]
    );
  }

  //UTILS
  toggleModal() {
    this.modal.classList.toggle("hidden");
    this.modal.classList.toggle("flex");
  }

  closeModal() {
    this.modal.classList.add("hidden");
    this.modal.classList.remove("flex");
  }

  openModal() {
    this.modal.classList.add("flex");
    this.modal.classList.remove("hidden");
  }
}

class Multiple {
  constructor(prefix) {
    this.prefix = prefix;
    this.container = document.querySelector("main");
    this.modalForm = document.querySelector(`[${this.prefix}-modal-form]`);
    this.lastGroup = "";
    this.init();
  }

  init() {
    window.addEventListener("load", () => {
      this.hiddenIfNoMultiples();
    });

    this.container.addEventListener("click", (e) => {
      //edit button
      try {
        if (
          e.target.closest("button").getAttribute("services-action") === "edit"
        ) {
          //avoid reupdate if same service
          const serviceName = e.target
            .closest("button")
            .getAttribute("services-name");
          if (this.lastGroup === serviceName) return;
          //else
          this.lastGroup = serviceName;
          //remove all multiples
          this.removeMultiples();
          //set multiple service values
          const servicesSettings = e.target
            .closest("[services-service]")
            .querySelector("[services-settings]")
            .getAttribute("value");
          const obj = JSON.parse(servicesSettings);
          this.updateModalMultiples(obj);
        }
      } catch (err) {}
    });

    this.modalForm.addEventListener("click", (e) => {
      //ADD BTN
      try {
        if (
          e.target.closest("button").hasAttribute(`${this.prefix}-multiple-add`)
        ) {
          //get plugin from btn
          const btn = e.target.closest("button");
          const serviceName = btn.getAttribute(`${this.prefix}-multiple-add`);
          //get all multiple groups
          const multipleEls = document.querySelectorAll(
            `[${this.prefix}-settings-multiple*="${serviceName}"]`
          );
          let count;
          //case no schema
          if (multipleEls.length <= 0) return;
          //case only schema
          if (multipleEls.length === 1) {
            count = 0;
          }
          //case schema and custom configs with num
          if (multipleEls.length > 1) {
            count = Number(
              multipleEls[1]
                .getAttribute(`${this.prefix}-settings-multiple`)
                .substring(
                  multipleEls[1].getAttribute(
                    `${this.prefix}-settings-multiple`
                  ).length - 1
                )
            );
          }
          //the default (schema) group is the last group
          const schema = document.querySelector(
            `[${this.prefix}-settings-multiple="${serviceName}_SCHEMA"]`
          );
          //clone it and change name by total - 1 (schema is hidden)
          const clone = schema.cloneNode(true);
          const name = clone
            .getAttribute("services-settings-multiple")
            .replace(`SCHEMA`, `${count + 1}`);
          clone.setAttribute("services-settings-multiple", name);
          this.showMultiple(clone);
          try {
            const cloneContainer = clone.querySelectorAll(
              "[setting-container]"
            );
            cloneContainer.forEach((ctnr) => {
              const newName = ctnr
                .getAttribute("setting-container")
                .replace("SCHEMA", `${count + 1}`);
              ctnr.setAttribute("setting-container", newName);
            });
          } catch (err) {}

          try {
            const cloneTitles = clone.querySelectorAll("h5");
            cloneTitles.forEach((title) => {
              title.textContent = `${title.textContent} #${count + 1}`;
            });
          } catch (err) {}

          const setNameID = ["input", "select"];

          setNameID.forEach((name) => {
            try {
              this.setNameIDloop(clone.querySelectorAll(name), count + 1);
            } catch (err) {}
          });

          //insert new group before first one
          schema.insertAdjacentElement("afterend", clone);
        }
      } catch (err) {}

      //REMOVE BTN
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`${this.prefix}-multiple-delete`)
        ) {
          const multContainer = e.target.closest(
            "[services-settings-multiple]"
          );
          multContainer.remove();
        }
        //remove last child
      } catch (err) {}
    });
  }

  updateModalMultiples(settings) {
    //keep only multiple settings value
    const multipleSettings = this.filterMultiple(settings);
    //put multiple on the right plugin, on schema container
    this.setMultipleToDOM(multipleSettings);
    //for each schema container, check if custom multiple (ending with _num)
    //and sort them on containers by nums
    //and check to keep default data (schema) or custom multiple value if exists
    this.sortMultiplesByNum();
    //remove custom multiple from schema to avoid them on add btn using schema container
    this.removeCustomFromSchema();
  }

  //keep only multiple settings value
  filterMultiple(settings) {
    const multiple = {};
    for (const [key, data] of Object.entries(settings)) {
      if (!isNaN(key[key.length - 1]) && key[key.length - 2] === "_") {
        multiple[key] = {
          value: data["value"],
          method: data["method"],
        };
      }
    }
    return multiple;
  }

  //put multiple on the right plugin, on schema container
  setMultipleToDOM(multiples) {
    //add them to the right plugin
    for (const [key, data] of Object.entries(multiples)) {
      const num = key[key.length - 1];
      const getSchemaKey = key.substring(0, key.length - 2);
      const getSchemaSetting = document.querySelector(
        `[setting-container="${getSchemaKey}_SCHEMA"]`
      );
      const cloneSchemaSetting = getSchemaSetting.cloneNode(true);
      //replace info
      cloneSchemaSetting.setAttribute("setting-container", key);
      const title = cloneSchemaSetting.querySelector("h5");
      title.textContent = `${title.textContent} #${num}`;
      //replace input info
      try {
        const inp = cloneSchemaSetting.querySelector("input");
        this.setNameID(inp, key);
      } catch (err) {}
      //or select
      try {
        const select = cloneSchemaSetting.querySelector("select");
        this.setNameID(select, key);
      } catch (err) {}
      getSchemaSetting.insertAdjacentElement("beforebegin", cloneSchemaSetting);
    }
  }

  //for each schema container, check if custom multiple (ending with _num)
  //and sort them on containers by nums
  //and check to keep default data (schema) or custom multiple value if exists
  sortMultiplesByNum() {
    const multiPlugins = document.querySelectorAll(
      `[${this.prefix}-settings-multiple*='SCHEMA']`
    );
    multiPlugins.forEach((defaultGrp) => {
      //get group number for the multiples settings
      const multipleEls = defaultGrp.querySelectorAll("[setting-container]");
      const multNum = new Set();
      multipleEls.forEach((setting) => {
        const name = setting.getAttribute("setting-container");
        if (!isNaN(name[name.length - 1])) multNum.add(name[name.length - 1]);
      });
      //create a different group for each number
      multNum.forEach((num) => {
        const newGroup = defaultGrp.cloneNode(true);
        this.showMultiple(newGroup);
        //change groupe name
        const currName = newGroup.getAttribute(
          `${this.prefix}-settings-multiple`
        );
        newGroup.setAttribute(
          `${this.prefix}-settings-multiple`,
          currName.replace("SCHEMA", num)
        );

        //remove elements that not fit num unless schema if no custom value
        const newGroupSettings = newGroup.querySelectorAll(
          "[setting-container]"
        );
        newGroupSettings.forEach((setting) => {
          //remove logic
          const settingName = setting.getAttribute("setting-container");
          if (
            (!settingName.endsWith(num) && !settingName.endsWith("SCHEMA")) ||
            (settingName.endsWith("SCHEMA") &&
              document.querySelector(`${settingName.replace("SCHEMA", num)}`))
          ) {
            return setting.remove();
          }
          //else update info by num
          setting.setAttribute(
            "setting-container",
            setting.getAttribute("setting-container").replace(`SCHEMA`, num)
          );
          const title = setting.querySelector("h5");
          if (!title.textContent.includes(`#${num}`))
            title.textContent = `${title.textContent} #${num}`;
          //replace input info

          const setNameID = ["input", "select"];

          setNameID.forEach((name) => {
            try {
              this.setNameID(
                setting.querySelector(name),
                setting.getAttribute("setting-container")
              );
            } catch (err) {}
          });
        });
        defaultGrp.insertAdjacentElement("afterend", newGroup);
      });
    });
  }

  removeCustomFromSchema() {
    const multiPlugins = document.querySelectorAll(
      `[${this.prefix}-settings-multiple*='SCHEMA']`
    );

    multiPlugins.forEach((defaultGrp) => {
      const multipleEls = defaultGrp.querySelectorAll("[setting-container]");
      multipleEls.forEach((setting) => {
        const settingName = setting.getAttribute("setting-container");
        if (!settingName.endsWith("SCHEMA")) setting.remove();
      });
    });
  }

  //UTILS

  hiddenIfNoMultiples() {
    //hide multiple btn if no multiple exist on a plugin
    const multiples = document.querySelectorAll(
      `[${this.prefix}-settings-multiple]`
    );
    multiples.forEach((container) => {
      if (container.querySelectorAll(`[setting-container]`).length <= 0)
        container.parentElement
          .querySelector("[multiple-handler]")
          .classList.add("hidden");
    });
  }

  removeMultiples() {
    const multiPlugins = document.querySelectorAll(
      `[${this.prefix}-settings-multiple]`
    );
    multiPlugins.forEach((multiGrp) => {
      if (
        !multiGrp.getAttribute("services-settings-multiple").includes("SCHEMA")
      )
        multiGrp.remove();
    });
  }

  showMultiple(el) {
    el.classList.add("grid");
    el.classList.remove("hidden");
  }

  setNameIDloop(iterable, value) {
    iterable.forEach((item) => {
      const currID = item.getAttribute("id");
      const currName = item.getAttribute("name");
      item.setAttribute("id", `${currID}_${value}`);
      item.setAttribute("name", `${currName}_${value}`);
    });
  }

  setNameID(el, value) {
    el.setAttribute("id", `${value}`);
    el.setAttribute("name", `${value}`);
  }
}

class FilterSettings {
  constructor(prefix) {
    this.prefix = prefix;
    this.input = document.querySelector("input#settings-filter");
    //DESKTOP
    this.deskTabs = document.querySelectorAll(`[${this.prefix}-item-handler]`);
    this.init();
  }

  init() {
    this.input.addEventListener("input", () => {
      this.resetFilter();
      //get inp format
      const inpValue = this.input.value.trim().toLowerCase();
      //loop all tabs
      this.deskTabs.forEach((tab) => {
        //get settings of tabs except multiples
        const settings = this.getSettingsFromTab(tab);

        //compare total count to currCount to determine
        //if tabs need to be hidden
        const settingCount = settings.length;
        let hiddenCount = 0;
        settings.forEach((setting) => {
          try {
            const title = setting
              .querySelector("h5")
              .textContent.trim()
              .toLowerCase();
            if (!title.includes(inpValue)) {
              setting.classList.add("hidden");
              hiddenCount++;
            }
          } catch (err) {}
        });
        //case no setting match, hidden tab and content
        if (settingCount === hiddenCount) {
          const tabName = tab.getAttribute(`${this.prefix}-item-handler`);
          //hide mobile and desk tabs
          tab.classList.add("hidden");
          document
            .querySelector(`[${this.prefix}-mobile-item-handler="${tabName}"]`)
            .classList.add("hidden");
          document
            .querySelector(`[${this.prefix}-item=${tabName}]`)
            .querySelector("[setting-header]")

            .classList.add("hidden");
        }
      });
    });
  }

  resetFilter() {
    this.deskTabs.forEach((tab) => {
      const tabName = tab.getAttribute(`${this.prefix}-item-handler`);
      //hide mobile and desk tabs
      tab.classList.remove("hidden");
      document
        .querySelector(`[${this.prefix}-mobile-item-handler="${tabName}"]`)
        .classList.remove("hidden");
      document
        .querySelector(`[${this.prefix}-item=${tabName}]`)
        .querySelector("[setting-header]")
        .classList.remove("hidden");
      const settings = this.getSettingsFromTab(tab);
      settings.forEach((setting) => {
        setting.classList.remove("hidden");
      });
    });
  }

  getSettingsFromTab(tabEl) {
    const tabName = tabEl.getAttribute(`${this.prefix}-item-handler`);
    const settingContainer = document
      .querySelector(`[${this.prefix}-item="${tabName}"]`)
      .querySelector(`[${this.prefix}-settings]`);
    const settings = settingContainer.querySelectorAll("[setting-container]");
    return settings;
  }
}

const setCheckbox = new Checkbox("[services-modal-form]");
const setSelect = new Select("[services-modal-form]", "services");
const setPopover = new Popover("main", "services");
const setTabs = new Tabs("[services-tabs]", "services");
const setModal = new ServiceModal();
const format = new FormatValue();
const setMultiple = new Multiple("services");
const setFilter = new FilterSettings("services");
