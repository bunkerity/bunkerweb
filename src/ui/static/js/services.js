import { Checkbox, Select, Password } from "./utils/form.js";
import {
  Popover,
  Tabs,
  FormatValue,
  FilterSettings,
} from "./utils/settings.js";

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

          if (action === "edit" || action === "new") {
            this.setForm(action, serviceName, this.formNewEdit);
          }

          if (action === "delete")
            this.setForm(action, serviceName, this.formDelete);

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

          if (action === "new") this.addOneMultGroup();
          this.openModal();
        }
      } catch (err) {}
    });
  }

  addOneMultGroup() {
    const settings = document.querySelector("[services-modal-form]");
    const multAddBtns = settings.querySelectorAll("[services-multiple-add]");
    multAddBtns.forEach((btn) => {
      //check if already one (SCHEMA exclude so length >= 2)
      const plugin = btn.closest("[plugin-item]");
      if (plugin.querySelectorAll("[services-settings-multiple]").length >= 2)
        return;
      btn.click();
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
    this.inputs.forEach((inp) => {
      let defaultVal = "";
      try {
        defaultVal = inp.getAttribute("default-value");
      } catch (err) {
        defaultVal = "";
      }

      let defaultMethod = "ui";
      try {
        defaultMethod = inp.getAttribute("default-method");
      } catch (err) {
        defaultMethod = "ui";
      }
      //SET METHOD
      this.setDisabled(inp, defaultMethod);

      //SET VALUE
      if (inp.getAttribute("type") === "checkbox") {
        inp.checked = defaultVal === "yes" ? true : false;
        inp.setAttribute("value", defaultVal);
        inp.value = defaultVal;
      }

      if (inp.getAttribute("type") !== "checkbox") {
        inp.setAttribute("value", defaultVal);
      }
    });

    this.selects.forEach((select) => {
      let defaultVal = "";
      try {
        defaultVal = select.getAttribute("default-value");
      } catch (err) {
        defaultVal = "";
      }

      let defaultMethod = "ui";
      try {
        defaultMethod = select.getAttribute("default-method");
      } catch (err) {
        defaultMethod = "ui";
      }

      if (defaultMethod === "ui" || defaultMethod === "default") {
        document
          .querySelector(
            `[setting-select=${select.getAttribute("setting-select-default")}]`
          )
          .removeAttribute("disabled");
      } else {
        document
          .querySelector(
            `[setting-select=${select.getAttribute("setting-select-default")}]`
          )
          .setAttribute("disabled", "");
      }
      select.parentElement
        .querySelector(
          `button[setting-select-dropdown-btn][value='${defaultVal}']`
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
        const inps = this.modal.querySelectorAll(`[name='${key}']`);

        inps.forEach((inp) => {
          //SET DISABLED / ENABLED
          this.setDisabled(inp, method);
          //SET VALUE
          //for regular input
          if (
            inp.tagName === "INPUT" &&
            inp.getAttribute("type") !== "checkbox"
          ) {
            inp.setAttribute("value", value);
            inp.value = value;
          }
          //for checkbox
          if (
            inp.tagName === "INPUT" &&
            inp.getAttribute("type") === "checkbox"
          ) {
            inp.checked = value === "yes" ? true : false;
            inp.setAttribute("value", value);
            if (inpt.hasAttribute("disabled")) {
              const hidden_inpt = inpt
                .closest("div[checkbox-handler]")
                .querySelector("input[type='hidden']");
              hidden_inpt.setAttribute("value", value);
            }
          }
          //for select
          if (inp.tagName === "SELECT") {
            inp.parentElement
              .querySelector(
                `button[setting-select-dropdown-btn][value='${value}']`
              )
              .click();
          }
        });
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

  sortMultipleByContainerAndSuffixe(obj) {
    const sortMultiples = {};
    for (const [name, value] of Object.entries(obj)) {
      //split name and check if there is a suffixe
      const splitName = name.split("_");
      //suffixe start with number 1, if none give arbitrary 0 value to store on same group
      const isSuffixe = !isNaN(splitName[splitName.length - 1]) ? true : false;
      const suffixe = isSuffixe ? splitName[splitName.length - 1] : "0";
      //remove suffix if exists and query related name_SCHEMA to get container info
      const nameSuffixLess = isSuffixe
        ? name.replace(`_${splitName[splitName.length - 1]}`, "").trim()
        : name.trim();
      const relateSetting = document.querySelector(
        `[setting-container=${nameSuffixLess}_SCHEMA]`
      );
      const relateCtnr = relateSetting.closest("[services-settings-multiple]");
      const relateCtnrName = relateCtnr.getAttribute(
        "services-settings-multiple"
      );
      //then we sort the setting on the right container name by suffixe number
      if (!(relateCtnrName in sortMultiples)) {
        sortMultiples[relateCtnrName] = {};
      }

      if (!(suffixe in sortMultiples[relateCtnrName])) {
        sortMultiples[relateCtnrName][suffixe] = {};
      }
      sortMultiples[relateCtnrName][suffixe][name] = value;
    }
    return sortMultiples;
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
          this.removePrevMultiples();
          //get multiple service values and parse as obj
          const servicesSettings = e.target
            .closest("[services-service]")
            .querySelector("[services-settings]")
            .getAttribute("value");
          const obj = JSON.parse(servicesSettings);
          //keep only multiple settings value
          const multipleSettings = this.getMultiplesOnly(obj);
          const sortMultiples =
            this.sortMultipleByContainerAndSuffixe(multipleSettings);
          this.setMultipleToDOM(sortMultiples);
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
          //default is 0
          let topNum = 0;
          //loop on curr multiples, get the name suffix for each
          //and keep the highest num
          multipleEls.forEach((container) => {
            const ctnrName = container.getAttribute(
              "services-settings-multiple"
            );
            const num = this.getSuffixNumOrFalse(ctnrName);
            if (!isNaN(num) && num > topNum) topNum = num;
          });
          //the final number is num
          //num is total - 1 because of hidden SCHEMA container
          const currNum = `${multipleEls.length >= 2 ? topNum + 1 : topNum}`;
          const setNum = +currNum === 0 ? `` : `_${currNum}`;
          //the default (schema) group is the last group
          const schema = document.querySelector(
            `[${this.prefix}-settings-multiple="${attName}_SCHEMA"]`
          );
          //clone schema to create a group with new num
          const schemaClone = schema.cloneNode(true);
          this.changeCloneSuffix(schemaClone, setNum);

          this.showClone(schema, schemaClone);
          //insert new group before first one
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
  setMultipleToDOM(sortMultObj) {
    //we loop on each multiple that contains values to render to DOM
    for (const [schemaCtnrName, multGroupBySuffix] of Object.entries(
      sortMultObj
    )) {
      //we need to access the DOM schema container
      const schemaCtnr = document.querySelector(
        `[services-settings-multiple="${schemaCtnrName}"]`
      );
      //now we have to loop on each multiple settings group
      for (const [suffix, settings] of Object.entries(multGroupBySuffix)) {
        //we have to clone schema container first
        const schemaCtnrClone = schemaCtnr.cloneNode(true);
        //now we replace _SCHEMA by current suffix everywhere we need
        //unless it is 0 that means no suffix
        const suffixFormat = +suffix === 0 ? `` : `_${suffix}`;
        this.changeCloneSuffix(schemaCtnrClone, suffixFormat);
        //then we have to loop on every settings of current group to change clone values by right ones
        for (const [name, data] of Object.entries(settings)) {
          //get setting container of clone container
          const settingContainer = schemaCtnrClone.querySelector(
            `[setting-container="${name}"]`
          );
          //replace input info
          this.setSetting(data["value"], data["method"], settingContainer);
        }
        //send schema clone to DOM and show it
        this.showClone(schemaCtnr, schemaCtnrClone);
      }
    }

    //disabled after update values and method
    this.setDisabled();
  }

  changeCloneSuffix(schemaCtnrClone, suffix) {
    //rename multiple container
    schemaCtnrClone.setAttribute(
      "services-settings-multiple",
      schemaCtnrClone
        .getAttribute("services-settings-multiple")
        .replace("_SCHEMA", suffix)
    );

    //rename title
    const titles = schemaCtnrClone.querySelectorAll("h5");
    titles.forEach((title) => {
      const text = title.textContent;
      title.textContent = `${text} ${
        suffix ? `#${suffix.replace("_", "")}` : ``
      }`;
    });

    //rename setting container
    const settingCtnrs = schemaCtnrClone.querySelectorAll(
      "[setting-container]"
    );
    settingCtnrs.forEach((settingCtnr) => {
      settingCtnr.setAttribute(
        "setting-container",
        settingCtnr.getAttribute("setting-container").replace("_SCHEMA", suffix)
      );
    });

    //rename input
    try {
      const inps = schemaCtnrClone.querySelectorAll("input");
      this.renameLoop(inps, suffix);
    } catch (err) {}

    //rename select
    try {
      const selects = schemaCtnrClone.querySelectorAll("select");
      this.renameLoop(selects, suffix);
    } catch (err) {}
  }

  renameLoop(inps, suffix) {
    inps.forEach((inp) => {
      const newName = inp.getAttribute("name").replace("_SCHEMA", suffix);
      inp.setAttribute("name", newName);
      if (inp.hasAttribute("id")) inp.setAttribute("id", newName);
    });
  }

  setSetting(value, method, settingContainer) {
    //update input
    try {
      const inps = settingContainer.querySelectorAll("input");
      inps.forEach((inp) => {
        if (inp.getAttribute("type") === "checkbox") {
          inp.checked = value === "yes" ? true : false;
          if (inp.hasAttribute("disabled")) {
            const hidden_inp = inp
              .closest("div[checkbox-handler]")
              .querySelector("input[type='hidden']");
            hidden_inp.setAttribute("value", value);
          }
        }

        inp.value = value;
        inp.setAttribute("default-method", method);
      });
    } catch (err) {}
    //update select
    try {
      const select = settingContainer.querySelector("select");
      const name = select.getAttribute("services-setting-select-default");
      const selTxt = document.querySelector(
        `[services-setting-select-text='${name}']`
      );

      selTxt.textContent = value;
      selTxt.setAttribute("value", value);
      const options = select.options;

      for (let i = 0; i < options.length; i++) {
        const option = options[i];
        option.value === value
          ? option.setAttribute("selected")
          : option.removeAttribute("selected");
      }
      select.setAttribute("default-method", method);
    } catch (err) {}
  }

  showClone(schemaCtnr, schemaCtnrClone) {
    schemaCtnr.insertAdjacentElement("afterend", schemaCtnrClone);
    schemaCtnrClone.classList.remove("hidden");
    schemaCtnrClone.classList.add("grid");
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

  removePrevMultiples() {
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

const setCheckbox = new Checkbox();
const setSelect = new Select();
const setPassword = new Password();

const setPopover = new Popover();
const setTabs = new Tabs();
const setModal = new ServiceModal();
const format = new FormatValue();
const setFilterGlobal = new FilterSettings(
  "settings-filter",
  "[service-content='settings']"
);

const setMultiple = new Multiple("services");
