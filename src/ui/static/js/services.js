import { Checkbox, Popover, Select, Tabs, FormatValue } from "./utils.js";

class ServiceModal {
  constructor() {
    //modal elements
    this.modal = document.querySelector("[services-modal]");
    this.modalTitle = this.modal.querySelector("[services-modal-title]");
    this.modalTabs = this.modal.querySelector(["[services-tabs]"]);
    this.modalCard = this.modal.querySelector("[services-modal-card]");
    //modal forms
    this.formNewEdit = this.modal.querySelector("[services-modal-form]");
    this.formDelete = this.modal.querySelector("[services-modal-form-delete]");
    //container
    this.container = document.querySelector("main");
    //general inputs
    this.inputs = this.modal.querySelectorAll("input[default-value]");
    this.selects = this.modal.querySelectorAll("select[default-value]");
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
      //delete button
      try {
        if (
          e.target.closest("button").getAttribute("services-action") ===
          "delete"
        ) {
          this.setDeleteForm(
            "delete",
            e.target.closest("button").getAttribute("service-name")
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
          this.setNewEditForm(
            "edit",
            e.target.closest("button").getAttribute("service-name")
          );
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

    this.formNewEdit.classList.remove("hidden");
    this.formDelete.classList.add("hidden");
  }

  showDeleteForm() {
    this.modalCard.classList.remove("h-[90vh]");
    this.modalCard.classList.remove("w-full");

    this.modalTabs.classList.remove("grid");
    this.modalTabs.classList.add("hidden");

    this.formNewEdit.classList.add("hidden");
    this.formDelete.classList.remove("hidden");
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
    this.container = document.querySelector(`[${this.prefix}-modal-form]`);
    this.init();
  }

  init() {
    this.container.addEventListener("click", (e) => {
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
            `[${this.prefix}-settings-multiple="${serviceName}"]`
          );
          const multipleCount = multipleEls.length;
          //the default (schema) group is the last group
          const schema = multipleEls[multipleEls.length - 1];
          //clone it and change name by total - 1 (schema is hidden)
          const clone = schema.cloneNode(true);
          const cloneTitles = clone.querySelectorAll("h5");
          const cloneInps = clone.querySelectorAll("input");
          const cloneSelects = clone.querySelectorAll("select");

          cloneTitles.forEach((title) => {
            title.textContent = `${title.textContent} #${multipleCount}`;
          });

          cloneInps.forEach((inp) => {
            const currID = inp.getAttribute("id");
            const currName = inp.getAttribute("name");
            inp.setAttribute("id", `${currID}_${multipleCount}`);
            inp.setAttribute("name", `${currName}_${multipleCount}`);
          });

          cloneSelects.forEach((select) => {
            const currID = select.getAttribute("id");
            const currName = select.getAttribute("name");
            select.setAttribute("id", `${currID}_${multipleCount}`);
            select.setAttribute("name", `${currName}_${multipleCount}`);
          });
          //insert new group before first one
          const firstMultiple = multipleEls[0];
          firstMultiple.insertAdjacentElement("beforebegin", clone);
        }
      } catch (err) {}

      //REMOVE BTN
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`${this.prefix}-multiple-delete`)
        ) {
          //remove the first element (last created)
          //unless it is the schema (length 1)
          const btn = e.target.closest("button");
          const serviceName = btn.getAttribute(
            `${this.prefix}-multiple-delete`
          );
          const multipleEls = document.querySelectorAll(
            `[${this.prefix}-settings-multiple="${serviceName}"]`
          );
          if (multipleEls.length === 1) return;
          const firstMultiple = multipleEls[0];
          firstMultiple.remove();
        }
        //remove last child
      } catch (err) {}
    });
  }
}

const setCheckbox = new Checkbox("[services-modal-form]");
const setSelect = new Select("[services-modal-form]", "services");
const setPopover = new Popover("main", "services");
const setTabs = new Tabs("[services-tabs]", "services");
const setModal = new ServiceModal();
const format = new FormatValue();
const setMultiple = new Multiple("services");
