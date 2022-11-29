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
    this.formRename = this.modal.querySelector("[services-modal-form-rename]");
    //container
    this.container = document.querySelector("main");
    //general inputs
    this.inputs = this.modal.querySelectorAll("input[default-value]");
    this.selects = this.modal.querySelectorAll("select[default-value]");
    this.lastGroup = "";

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
      //rename button
      try {
        if (
          e.target.closest("button").getAttribute("services-action") ===
          "rename"
        ) {
          this.setRenameForm(
            "rename",
            e.target.closest("button").getAttribute("services-name")
          );
          this.openModal();
        }
      } catch (err) {}
      //delete button
      try {
        if (
          e.target.closest("button").getAttribute("services-action") ===
          "delete"
        ) {
          this.setRenameForm(
            "rename",
            e.target.closest("button").getAttribute("services-name")
          );
          this.openModal();
        }
      } catch (err) {}
      //new button
      try {
        if (
          e.target.closest("button").getAttribute("services-action") === "new"
        ) {
          this.setNewEditForm("new", "service");
          this.setDefaultValue();
          this.openModal();
        }
      } catch (err) {}
      //edit button
      try {
        if (
          e.target.closest("button").getAttribute("services-action") === "edit"
        ) {
          //no reupdate if same service
          const serviceName = e.target
            .closest("button")
            .getAttribute("services-name");

          if (this.lastGroup === serviceName) return this.openModal();
          //else
          this.lastGroup = serviceName;
          this.setNewEditForm("edit", serviceName);
          //change this to hidden config on service card later
          const servicesSettings = e.target
            .closest("[services-service]")
            .querySelector("[services-settings]")
            .getAttribute("value");
          this.setDefaultValue();
          const obj = JSON.parse(servicesSettings);
          this.updateModalData(obj);
          this.openModal();
        }
      } catch (err) {}
    });
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
  }

  setDisabled(inp, method) {
    if (method === "ui" || method === "default") {
      inp.removeAttribute("disabled");
    } else {
      inp.setAttribute("disabled", "");
    }
  }

  setNewEditForm(action, serviceName) {
    this.showNewEditForm();
    this.modalTitle.textContent = `${action} ${serviceName}`;
    this.formNewEdit.setAttribute("id", `form-${action}-${serviceName}`);
    this.formNewEdit
      .querySelector(`input[name="operation"]`)
      .setAttribute("value", action);
    this.formNewEdit
      .querySelector(`input[name="OLD_SERVER_NAME"]`)
      .setAttribute("value", serviceName);
  }

  setRenameForm(action, serviceName) {
    this.showRenameForm();
    this.modalTitle.textContent = `${action} ${serviceName}`;
    this.formRename.setAttribute("id", `form-${action}-${serviceName}`);
    this.formRename
      .querySelector(`input[name="OLD_SERVER_NAME"]`)
      .setAttribute("value", serviceName);
    this.formRename
      .querySelector(`input[name="SERVER_NAME"]`)
      .setAttribute("value", serviceName);
  }

  setDeleteForm(action, serviceName) {
    this.showDeleteForm();
    this.modalTitle.textContent = `${action} ${serviceName}`;
    this.formDelete.setAttribute("id", `form-${action}-${serviceName}`);
    this.formDelete
      .querySelector(`input[name="SERVER_NAME"]`)
      .setAttribute("value", serviceName);
    this.formDelete.querySelector(
      `[services-modal-text]`
    ).textContent = `Are you sure you want to delete ${serviceName} ?`;
  }

  showNewEditForm() {
    this.modalCard.classList.add("h-[90vh]");
    this.modalCard.classList.add("w-full");

    this.modalTabs.classList.add("grid");
    this.modalTabs.classList.remove("hidden");
    this.modalTabsHeader.classList.add("flex");
    this.modalTabsHeader.classList.remove("hidden");

    this.formNewEdit.classList.remove("hidden");
    this.formDelete.classList.add("hidden");
    this.formRename.classList.add("hidden");
  }

  showDeleteForm() {
    this.modalCard.classList.remove("h-[90vh]");
    this.modalCard.classList.remove("w-full");

    this.modalTabs.classList.remove("grid");
    this.modalTabs.classList.add("hidden");

    this.modalTabsHeader.classList.remove("flex");
    this.modalTabsHeader.classList.add("hidden");

    this.formNewEdit.classList.add("hidden");
    this.formRename.classList.add("hidden");

    this.formDelete.classList.remove("hidden");
  }

  showRenameForm() {
    this.modalCard.classList.remove("h-[90vh]");
    this.modalCard.classList.remove("w-full");

    this.modalTabs.classList.remove("grid");
    this.modalTabs.classList.add("hidden");

    this.modalTabsHeader.classList.remove("flex");
    this.modalTabsHeader.classList.add("hidden");

    this.formNewEdit.classList.add("hidden");
    this.formDelete.classList.add("hidden");

    this.formRename.classList.remove("hidden");
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
          inpt.checked = defaultVal === "yes" ? true : false;
          inpt.setAttribute("value", defaultVal);
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
