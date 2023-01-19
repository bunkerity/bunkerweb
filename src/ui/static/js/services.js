import { Checkbox, Select, Password } from "./utils/form.js";
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
          const attName = btn.getAttribute(`${this.prefix}-multiple-add`);
          //get all multiple groups
          const multipleEls = document.querySelectorAll(
            `[${this.prefix}-settings-multiple*="${attName}"]`
          );
          //case no schema
          if (multipleEls.length <= 0) return;

          //get the next container number logic
          let topNum = 0;

          multipleEls.forEach((container) => {
            const ctnrName = container.getAttribute(
              "services-settings-multiple"
            );
            const num = this.getSuffixNumOrFalse(ctnrName);
            if (!isNaN(num) && num > topNum) topNum = num;
          });
          //num is total - 1 or nothing if none
          const setNum = `${multipleEls.length >= 2 ? topNum + 1 : topNum}`;

          //the default (schema) group is the last group
          const schema = document.querySelector(
            `[${this.prefix}-settings-multiple="${attName}_SCHEMA"]`
          );
          //clone schema to create a group with new num
          const clone = schema.cloneNode(true);
          const name = clone
            .getAttribute("services-settings-multiple")
            .replace(`SCHEMA`, `${setNum}`);
          clone.setAttribute("services-settings-multiple", name);
          this.showMultiple(clone);
          try {
            const cloneContainer = clone.querySelectorAll(
              "[setting-container]"
            );
            cloneContainer.forEach((ctnr) => {
              const newName = ctnr
                .getAttribute("setting-container")
                .replace("SCHEMA", `${setNum}`);
              ctnr.setAttribute("setting-container", newName);
              //rename input
              try {
                const inp = ctnr.querySelector("input");
                const newInpName = inp
                  .getAttribute("name")
                  .replace("_SCHEMA", "");
                inp.setAttribute("name", newInpName);
                inp.setAttribute("id", newInpName);
              } catch (err) {}
              //rename select
              try {
                const select = ctnr.querySelector("select");
                const newInpName = select
                  .getAttribute("name")
                  .replace("_SCHEMA", "");
                select.setAttribute("name", newInpName);
                select.setAttribute("id", newInpName);
              } catch (err) {}
            });
          } catch (err) {}

          try {
            const cloneTitles = clone.querySelectorAll("h5");
            cloneTitles.forEach((title) => {
              title.textContent = `${title.textContent} ${
                multipleEls.length >= 2 ? `#${topNum + 1}` : ``
              }`;
            });
          } catch (err) {}

          const setNameID = ["input", "select"];

          setNameID.forEach((name) => {
            try {
              this.setNameIDloop(clone.querySelectorAll(name), setNum);
            } catch (err) {}
          });

          //insert new group before first one
          schema.insertAdjacentElement("afterend", clone);
          //show all groups
          this.showMultByAtt(attName);
        }
      } catch (err) {}

      //TOGGLE BTN
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`${this.prefix}-multiple-toggle`)
        ) {
          const att = e.target
            .closest("button")
            .getAttribute(`${this.prefix}-multiple-toggle`);
          this.toggleMultByAtt(att);
        }
        //remove last child
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

  showMultByAtt(att) {
    const multContainers = document.querySelectorAll(
      `[services-settings-multiple^=${att}]`
    );
    multContainers.forEach((container) => {
      if (
        !container.getAttribute("services-settings-multiple").includes("SCHEMA")
      )
        container.classList.remove("hidden");
    });
  }

  toggleMultByAtt(att) {
    const multContainers = document.querySelectorAll(
      `[services-settings-multiple^=${att}]`
    );
    multContainers.forEach((container) => {
      if (
        !container.getAttribute("services-settings-multiple").includes("SCHEMA")
      )
        container.classList.toggle("hidden");
    });
  }

  updateModalMultiples(settings) {
    //keep only multiple settings value
    const multipleSettings = this.getMultiplesOnly(settings);
    //put multiple on the right plugin, on schema container
    this.setMultipleToDOM(multipleSettings);
  }

  getMultiplesOnly(settings) {
    //get schema settings
    const multiples = {};
    const schemaSettings = document.querySelectorAll(
      `[setting-container$="SCHEMA"]`
    );
    // loop on every schema settings
    schemaSettings.forEach((schema) => {
      const schemaName = schema
        .getAttribute("setting-container")
        .replace("_SCHEMA", "")
        .trim();
      //check if match with service setting
      for (const [key, data] of Object.entries(settings)) {
        if (key.includes(schemaName)) {
          multiples[key] = {
            value: data["value"],
            method: data["method"],
          };
        }
      }
    });
    return multiples;
  }

  //put multiple on the right plugin, on schema container
  setMultipleToDOM(multiples) {
    const schemaSettings = document.querySelectorAll(
      `[setting-container$="SCHEMA"]`
    );
    schemaSettings.forEach((schema) => {
      const schemaName = this.getSchemaName(schema);
      //add all custom settings to DOM on schema container
      for (const [key, data] of Object.entries(multiples)) {
        //get num if exists or false
        const num = this.getSuffixNumOrFalse(key);
        //clone schema to create custom setting multiple
        if (key.includes(schemaName)) {
          const cloneSetting = schema.cloneNode(true);
          cloneSetting.setAttribute("setting-container", `${key}`);
          const title = cloneSetting.querySelector("h5");
          title.textContent = `${title.textContent} ${num ? `#${num}` : ``}`;
          this.setInpInfo(cloneSetting, key, data);
          //get the num, check if a container with this num exist
          //if not create new container and replace schema data by the one
          //if already exist, just change schema value by new one
          const schemaContainer = schema.closest(
            "[services-settings-multiple]"
          );
          const containerName = schemaContainer
            .getAttribute("services-settings-multiple")
            .replace("_SCHEMA", "");

          //case no container, create one
          if (
            !document.querySelector(
              `[services-settings-multiple="${containerName}${
                num ? `_${num}` : ""
              }"]`
            )
          ) {
            this.createContainer(
              schemaContainer,
              schemaName,
              cloneSetting,
              containerName,
              num
            );
          } else {
            //case container, add setting only
            this.addCustomToContainer(
              schemaName,
              containerName,
              cloneSetting,
              num
            );
          }
        }
      }
      //check enabled/disabled
      this.setDisabled();
    });
  }

  setInpInfo(cloneSetting, key, data) {
    //replace input info
    try {
      const inp = cloneSetting.querySelector("input");
      this.setNameID(inp, key);

      if (inp.getAttribute("type") === "checkbox") {
        if (data["value"] === "yes") inp.setAttribute("checked", "");
        if (data["value"] === "no") inp.removeAttribute("checked");
        inp.setAttribute("default-method", data["method"]);
      }

      if (inp.getAttribute("type") !== "checkbox") {
        inp.setAttribute("value", data["value"]);
        inp.setAttribute("default-method", data["method"]);
      }
    } catch (err) {}
    //or select
    try {
      const select = cloneSetting.querySelector("select");
      this.setNameID(select, key);
      const name = select.getAttribute("services-setting-select-default");
      const selTxt = document.querySelector(
        `[services-setting-select-text='${name}']`
      );

      selTxt.textContent = data["value"];
      selTxt.setAttribute("value", data["value"]);
      const options = select.options;

      for (let i = 0; i < options.length; i++) {
        const option = options[i];
        option.value === data["value"]
          ? option.setAttribute("selected")
          : option.removeAttribute("selected");
      }
      inp.setAttribute("default-method", data["method"]);
    } catch (err) {}
  }

  addCustomToContainer(schemaName, containerName, cloneSetting, num) {
    const customContainer = document.querySelector(
      `[services-settings-multiple="${containerName}${num ? `_${num}` : ""}"]`
    );
    const cloneSchema = customContainer.querySelector(
      `[setting-container*=${schemaName}]`
    );
    cloneSchema.insertAdjacentElement("beforebegin", cloneSetting);
    cloneSchema.remove();
  }

  createContainer(
    schemaContainer,
    schemaName,
    cloneSetting,
    containerName,
    num
  ) {
    const cloneSchemaCtnr = schemaContainer.cloneNode(true);
    cloneSchemaCtnr.setAttribute(
      "services-settings-multiple",
      `${containerName}${num ? `_${num}` : ""}`
    );
    //get the schema setting clone element and replace it by custom setting
    const cloneSchema = cloneSchemaCtnr.querySelector(
      `[setting-container*=${schemaName}]`
    );
    cloneSchema.insertAdjacentElement("beforebegin", cloneSetting);
    cloneSchema.remove();
    //replace schema suffix by right suffix
    const settings = cloneSchemaCtnr.querySelectorAll("[setting-container]");
    settings.forEach((setting) => {
      //change title
      const title = setting.querySelector("h5");
      title.textContent = title.textContent.includes(`${num ? `#${num}` : ``}`)
        ? title.textContent
        : `${title.textContent} ${num ? `#${num}` : ``}`;
      //change att
      setting.setAttribute(
        "setting-container",
        setting
          .getAttribute("setting-container")
          .replace("_SCHEMA", `${num ? `_${num}` : ``}`)
      );
      //replace name and id att too
      const newName = setting.getAttribute("setting-container");
      //replace input info
      try {
        const inp = setting.querySelector("input");
        this.setNameID(inp, newName);
      } catch (err) {}
      //or select
      try {
        const select = setting.querySelector("select");
        this.setNameID(select, newName);
      } catch (err) {}
      try {
      } catch (err) {}
    });
    schemaContainer.insertAdjacentElement("afterend", cloneSchemaCtnr);
    cloneSchemaCtnr.classList.remove("hidden");
    cloneSchemaCtnr.classList.add("grid");
  }

  setDisabled() {
    const multipleCtnr = document.querySelectorAll(
      "[services-settings-multiple]"
    );
    multipleCtnr.forEach((container) => {
      const settings = container.querySelectorAll("[setting-container]");

      settings.forEach((setting) => {
        //replace input info
        try {
          const inp = setting.querySelector("input");
          const method = inp.getAttribute("default-method");
          if (method === "ui" || method === "default") {
            inp.removeAttribute("disabled");
          } else {
            inp.setAttribute("disabled", "");
          }
        } catch (err) {}
        //or select
        try {
          const select = setting.querySelector("select");
          const method = select.getAttribute("default-method");
          const name = select.getAttribute("services-setting-select-default");
          const selDOM = document.querySelector(
            `button[services-setting-select='${name}']`
          );
          if (method === "ui" || method === "default") {
            selDOM.setAttribute("disabled", "");
          } else {
            selDOM.setAttribute("disabled", "");
          }
        } catch (err) {}
      });
    });
  }

  //UTILS

  getSuffixNumOrFalse(name) {
    const num = !isNaN(Number(name.substring(name.lastIndexOf("_") + 1)))
      ? Number(name.substring(name.lastIndexOf("_") + 1))
      : "";
    return num;
  }

  getSchemaName(schemaCtnr) {
    return schemaCtnr
      .getAttribute("setting-container")
      .replace("_SCHEMA", "")
      .trim();
  }

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
const setPassword = new Password();

const setPopover = new Popover("main", "services");
const setTabs = new Tabs("[services-tabs]", "services");
const setModal = new ServiceModal();
const format = new FormatValue();
const setMultiple = new Multiple("services");
const setFilter = new FilterSettings("services");
