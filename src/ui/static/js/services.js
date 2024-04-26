import {
  Popover,
  TabsSelect,
  FormatValue,
  FilterSettings,
  CheckNoMatchFilter,
  showInvalid,
} from "./utils/settings.js";

class Settings {
  constructor(formEl, mode = "advanced", prefix = "services") {
    this.prefix = prefix;
    this.mode = mode;
    this.multSettingsName = JSON.parse(
      document
        .querySelector("input[data-plugins-multiple]")
        .getAttribute("data-plugins-multiple")
        .replaceAll(`'`, `"`),
    );
    //modal elements
    this.container = formEl;
    this.switchModeBtn =
      document.querySelector("[data-toggle-settings-mode-btn]") || null;

    this.submitBtn = this.container.querySelector(
      `button[data-${this.prefix}-modal-submit]`,
    );

    this.darkMode = document.querySelector("[data-dark-toggle]");
    this.isDarkMode = this.darkMode.checked;

    if (this.mode === "simple") {
      this.nextBtn = this.container.querySelector("button[data-simple-next]");
      this.backBtn = this.container.querySelector("button[data-simple-back]");
    }

    this.serverNameInps = this.container.querySelectorAll(
      'input[name="SERVER_NAME"][data-setting-input]',
    );

    // add editor for configs in simple mode
    this.editorEls = [];
    this.currAction = "";
    this.currMethod = "";
    this.oldServName = "";

    this.init();
  }

  init() {
    window.addEventListener("load", () => {
      this.hiddenIfNoMultiples();
      this.initEditors();
    });
    // Get list of server name from services card
    // When the server name input is matching existing server name that is not the current modal one
    // Disable the submit button
    window.addEventListener("DOMContentLoaded", () => {
      this.container.addEventListener("input", (e) => {
        this.checkVisibleInpsValidity();
      });
    });

    this.darkMode.addEventListener("click", (e) => {
      this.isDarkMode = e.target.checked;
      this.updateEditorMode();
    });

    // MODAL ACTIONS
    window.addEventListener("click", (e) => {
      //edit / clone action
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-action`) === "edit" ||
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-action`) === "clone"
        ) {
          this.updateData(e.target, false, false, false);
        }
      } catch (err) {
        console.log(err);
      }
      //new action
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-action`) === "new"
        ) {
          this.updateData(e.target, true, true, true, true);
        }
      } catch (err) {
        console.log(err);
      }
      // security
      try {
        if (
          e.target
            .closest("button")
            .getAttribute("data-setting-select-dropdown-btn") ==
          "security-level"
        ) {
          this.updateData(e.target, true, true, true, false);
        }
      } catch (err) {}
    });

    // SIMPLE MODE ACTIONS
    if (this.mode === "simple") {
      this.nextBtn.addEventListener("click", () => {
        this.nextSimpleStep();
      });

      this.backBtn.addEventListener("click", () => {
        this.prevSimpleStep();
      });
    }

    if (this.switchModeBtn) {
      this.switchModeBtn.addEventListener("click", () => {
        setTimeout(() => {
          this.checkVisibleInpsValidity();
        }, 20);
      });
    }

    // MULTIPLE ACTIONS
    this.container.addEventListener("click", (e) => {
      // Add btn
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`data-${this.prefix}-multiple-add`)
        ) {
          //get plugin from btn
          const btn = e.target.closest("button");
          const attName = btn.getAttribute(`data-${this.prefix}-multiple-add`);
          //get all multiple groups
          const multipleEls = this.container.querySelectorAll(
            `[data-${this.prefix}-settings-multiple*="${attName}"]`,
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
              `data-${this.prefix}-settings-multiple`,
            );
            const num = this.getSuffixNumOrFalse(ctnrName);
            if (!isNaN(num) && num > topNum) topNum = num;
          });
          //the final number is num
          //num is total - 1 because of hidden SCHEMA container
          const currNum = `${multipleEls.length >= 2 ? topNum + 1 : topNum}`;
          const setNum = +currNum === 0 ? `` : `_${currNum}`;
          //the default (schema) group is the last group
          const schema = this.container.querySelector(
            `[data-${this.prefix}-settings-multiple="${attName}_SCHEMA"]`,
          );
          //clone schema to create a group with new num
          const schemaClone = schema.cloneNode(true);

          //add special attribute for disabled logic
          this.changeCloneSuffix(schemaClone, setNum);
          //set disabled / enabled state
          this.setDisabledMultNew(schemaClone);
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
            .hasAttribute(`data-${this.prefix}-multiple-toggle`)
        ) {
          const att = e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-multiple-toggle`);
          this.toggleMultByAtt(att);
        }
        //remove last child
      } catch (err) {}

      //REMOVE BTN
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`data-${this.prefix}-multiple-delete`)
        ) {
          // We are not removing it really, just hiding it and update values to default
          // By setting default value, group will be send to server and delete (because a setting with default value is useless to keep)
          const multContainer = e.target.closest(
            `[data-${this.prefix}-settings-multiple]`,
          );
          multContainer.classList.add("hidden-multiple");
          // get setting container
          const settings = multContainer.querySelectorAll(
            `[data-setting-container]`,
          );
          settings.forEach((setting) => {
            // for regular input
            try {
              const inps = setting.querySelectorAll("input");
              inps.forEach((inp) => {
                // case checkbox
                if (inp.getAttribute("type") === "checkbox") {
                  const defaultVal = inp.getAttribute("data-default") || "";

                  if (defaultVal === "yes" && !inp.checked) {
                    inp.click();
                  }
                }

                // case regular
                if (inp.getAttribute("type") !== "checkbox") {
                  const defaultVal = inp.getAttribute("data-default") || "";
                  inp.setAttribute("value", defaultVal);
                  inp.value = defaultVal;
                }
              });
            } catch (e) {}
            // for select
            try {
              const selects = setting.querySelectorAll(
                "button[data-setting-select]",
              );
              selects.forEach((select) => {
                const defaultVal = select.getAttribute("data-default") || "";
                select
                  .querySelector("data-setting-select-text")
                  .setAttribute("data-value", defaultVal);
                select.querySelector("data-setting-select-text").textContent =
                  defaultVal;
                const dropdown = this.container.querySelector(
                  `[data-setting-select-dropdown="${select.getAttribute(
                    "data-setting-select",
                  )}"]`,
                );
                dropdown.querySelector(`button[value=${defaultVal}]`).click();
              });
            } catch (e) {}
          });
        }
        //remove last child
      } catch (err) {}
    });
  }

  resetSimpleMode() {
    // reset button
    this.backBtn.setAttribute("disabled", "");
    this.nextBtn.removeAttribute("disabled");
    // hidden all steps and show first one
    const steps = this.simpleForm.querySelectorAll("[data-step]");
    steps.forEach((step) => {
      step.classList.add("hidden");
    });
    const firstStep = this.simpleForm.querySelector("[data-step='1']");
    firstStep.classList.remove("hidden");
    this.updateSimpleActions();
  }

  initEditors() {
    const editors = this.container.querySelectorAll("[data-editor]");
    editors.forEach((editorEl) => {
      const editor = ace.edit(editorEl.getAttribute("id"));
      // Handle
      if (this.isDarkMode) {
        editor.setTheme("ace/theme/dracula");
      } else {
        editor.setTheme("ace/theme/dawn");
      }
      //editor options
      editor.setShowPrintMargin(false);
      this.editorEls.push(editor);
    });
  }

  updateEditorMode() {
    this.editorEls.forEach((editor) => {
      if (this.isDarkMode) {
        editor.setTheme("ace/theme/dracula");
      } else {
        editor.setTheme("ace/theme/dawn");
      }
    });
  }

  nextSimpleStep() {
    // get current step
    const currStep = this.container.querySelector("[data-step]:not(.hidden)");
    const currStepNum = currStep.getAttribute("data-step");
    // get next step and  next step + 1 to determine if continue or save
    const nextStep = this.container.querySelector(
      `[data-step="${+currStepNum + 1}"]`,
    );
    // hide current step and show next one
    currStep.classList.add("hidden");
    nextStep.classList.remove("hidden");

    this.checkVisibleInpsValidity();
    this.updateSimpleActions();
  }

  prevSimpleStep() {
    // get current step
    const currStep = this.container.querySelector("[data-step]:not(.hidden)");
    const currStepNum = currStep.getAttribute("data-step");
    // get next step and  next step + 1 to determine if continue or save
    const prevStep = this.container.querySelector(
      `[data-step="${+currStepNum - 1}"]`,
    );

    // hide current step and show next one
    currStep.classList.add("hidden");
    prevStep.classList.remove("hidden");

    this.checkVisibleInpsValidity();
    this.updateSimpleActions();
  }

  updateSimpleActions() {
    const currStep = this.container.querySelector("[data-step]:not(.hidden)");
    const currStepNum = currStep.getAttribute("data-step");
    // get next step and  next step + 1 to determine if continue or save
    const prevStep = this.container.querySelector(
      `[data-step="${+currStepNum - 1}"]`,
    );

    const nextStep = this.container.querySelector(
      `[data-step="${+currStepNum + 1}"]`,
    );

    // Handle case last step or not
    if (nextStep) {
      this.nextBtn.classList.remove("hidden");
      this.saveSimpleBtn.classList.add("hidden");
    }

    if (!nextStep) {
      this.nextBtn.classList.add("hidden");
      this.saveSimpleBtn.classList.remove("hidden");
    }

    if (prevStep) {
      this.backBtn.removeAttribute("disabled");
    }

    if (!prevStep) {
      this.backBtn.setAttribute("disabled", "");
    }
  }

  resetFilterInp() {
    const inpFilter = document.querySelector('input[name="settings-filter"]');
    inpFilter.value = "";
    inpFilter.dispatchEvent(new Event("input"));
  }

  changeSubmitBtn(action) {
    if (action === "delete") return;
    const text = action === "edit" ? "SAVE" : "CREATE";
  }

  resetServerName() {
    this.serverNameInps.forEach((inpServName) => {
      inpServName.getAttribute("value", "");
      inpServName.removeAttribute("disabled", "");
      inpServName.value = "";
    });
  }

  isAvoidInpList(type, inp, inpName, containerEl) {
    if (type === "input") {
      if (
        inpName === "csrf_token" ||
        inpName === "OLD_SERVER_NAME" ||
        inpName === "mode" ||
        inpName === "security-level" ||
        inpName === "is_draft" ||
        inpName === "operation" ||
        inpName === "settings-filter" ||
        inp.hasAttribute("data-combobox") ||
        (this.mode === "simple" && inpName === "SERVER_NAME")
      )
        return true;
    }

    if (type === "select") {
      if (
        inpName === "csrf_token" ||
        inpName === "OLD_SERVER_NAME" ||
        inpName === "mode" ||
        inpName === "security-level" ||
        inpName === "is_draft" ||
        inpName === "operation" ||
        inpName === "settings-filter" ||
        inp.hasAttribute("data-combobox") ||
        (this.mode === "simple" && inpName === "SECURITY_LEVEL")
      )
        return true;
    }

    return false;
  }

  setCheckbox(inp, method, value) {
    if (inp.getAttribute("type") === "checkbox" && inp.tagName === "INPUT") {
      try {
        if (inp.hasAttribute("aria-checked")) {
          value === "yes"
            ? inp.setAttribute("aria-checked", "true")
            : inp.setAttribute("aria-checked", "false");
        }
      } catch (err) {}

      try {
        value === "yes"
          ? inp.setAttribute("data-checked", "true")
          : inp.setAttribute("data-checked", "false");
      } catch (err) {}

      inp.setAttribute("value", value);
      inp.setAttribute("data-method", method);
      inp.checked = true;
    }
  }

  setInput(inp, method, value) {
    if (inp.getAttribute("type") !== "checkbox" && inp.tagName === "INPUT") {
      inp.setAttribute("value", value);
      inp.value = value;
      inp.setAttribute("data-method", method);
    }
  }

  // By default, loop on all settings to disabled them
  setSettingsByAtt(
    parentEl = this.container,
    attMethodName = "data-default-method",
    attValueName = "data-default-value",
    avoidMultiple = true,
  ) {
    // Start with input-like (input, checkbox)
    const inps = avoidMultiple
      ? parentEl.querySelectorAll("input:not([data-is-multiple])")
      : parentEl.querySelectorAll("input");
    inps.forEach((inp) => {
      // form related values are excludes
      const inpName = inp.getAttribute("name");
      if (this.isAvoidInpList("input", inp, inpName, parentEl)) return;

      //for all other settings values
      const defaultMethod = inp.getAttribute(attMethodName);
      const defaultVal = inp.getAttribute(attValueName);

      this.setCheckbox(inp, defaultMethod, defaultVal);
      this.setInput(inp, defaultMethod, defaultVal);

      this.setDisabledByMethod(inp, defaultMethod);
    });

    // Select only
    const selects = avoidMultiple
      ? parentEl.querySelectorAll("select:not([data-is-multiple])")
      : parentEl.querySelectorAll("select");
    selects.forEach((select) => {
      if (
        this.isAvoidInpList(
          "select",
          select,
          select.getAttribute("name"),
          parentEl,
        )
      )
        return;

      const defaultMethod = select.getAttribute(attMethodName);
      const defaultVal = select.getAttribute(attValueName);
      //click the custom select dropdown to update select value
      select.parentElement
        .querySelector(
          `button[data-setting-select-dropdown-btn][value='${defaultVal}']`,
        )
        .click();

      //set state to custom visible el
      const btnCustom = document.querySelector(
        `[data-setting-select=${select.getAttribute(
          "data-setting-select-default",
        )}]`,
      );

      this.setDisabledByMethod(btnCustom, defaultMethod);
    });
  }

  setDisabledByMethod(inp, method) {
    if (method === "ui" || method === "default") {
      inp.removeAttribute("disabled");
    } else {
      inp.setAttribute("disabled", "");
    }
  }

  updateOldNameValue() {
    const oldNameValue = this.action === "edit" ? this.oldServName : "";

    const oldNameInps = this.container.querySelectorAll(
      'input[name="OLD_SERVER_NAME"]',
    );

    oldNameInps.forEach((inp) => {
      inp.setAttribute("value", oldNameValue);
      inp.value = oldNameValue;
    });
  }

  updateOperation(operation) {
    // update operation and other hidden inputs for all mode in modal
    const operationInps = this.container.querySelectorAll(
      'input[name="operation"]',
    );
    operationInps.forEach((inp) => {
      inp.setAttribute("value", operation);
      inp.value = operation;
    });
  }

  // Switch settings mode and update button
  setSettingMode(mode) {
    if (this.mode === mode) return;
    if (!this.switchModeBtn) return;

    const elsToShow =
      mode === "advanced"
        ? document.querySelectorAll("[data-advanced]")
        : document.querySelectorAll("[data-simple]");
    const elsToHide =
      mode === "advanced"
        ? document.querySelectorAll("[data-simple]")
        : document.querySelectorAll("[data-advanced]");
    elsToHide.forEach((setting) => {
      setting.classList.add("!hidden");
    });
    elsToShow.forEach((setting) => {
      setting.classList.remove("!hidden");
    });
    // button
    this.switchModeBtn.setAttribute("data-toggle-settings-mode-btn", mode);
    const switchEls = this.switchModeBtn.querySelectorAll(
      "[data-toggle-settings-mode]",
    );
    switchEls.forEach((el) => {
      el.getAttribute("data-toggle-settings-mode") === mode
        ? el.classList.remove("hidden")
        : el.classList.add("hidden");
    });
  }

  updateData(
    target,
    forceEnabled = false,
    setMethodUI = false,
    emptyServerName = false,
  ) {
    // Get global needed data
    this.currAction = target
      .closest("button")
      .getAttribute(`data-${this.prefix}-action`);

    this.oldServName = "";
    if (this.currAction !== "new")
      this.oldServName = target
        .closest(`[data-${this.prefix}-service]`)
        .querySelector("[data-old-name]")
        .getAttribute("data-value");

    // Update metadata, hidden inputs and visual content
    const operation = this.currAction === "clone" ? "new" : this.currAction;
    this.updateOperation(this.currAction === "clone" ? "new" : this.currAction);
    this.updateOldNameValue();
    this.changeSubmitBtn();

    // Reset all settings
    this.setSettingsByAtt();

    // Override default settings by current security level
    const targetSettings = target
      .closest("[data-settings]")
      .getAttribute("data-settings");
    const settings = JSON.parse(targetSettings);
    console.log(settings);
    this.setRegularInps(settings, forceEnabled, setMethodUI, emptyServerName);
    this.setMultipleInps(settings);

    // Reset simple mode, we want to override default value by default security level
    if (this.mode === "simple") this.resetSimpleMode();

    // Global reset
    this.resetFilterInp();
    if (emptyServerName) this.resetServerName();
  }

  // Avoid multiple settings because it is handle by Multiple class
  getRegularInps(settings) {
    this.multSettingsName.forEach((name) => {
      // check if a settings is starting with a multiple name
      // if yes, remove it
      for (const [key, value] of Object.entries(settings)) {
        if (key.startsWith(name)) {
          delete settings[key];
        }
      }
    });
    return settings;
  }

  setRegularInps(allSettings, forceEnabled, setMethodUI) {
    const settings = this.getRegularInps(allSettings);
    // Case we have settings, like when we edit a service
    // We need to update the settings with the right values
    if (Object.keys(settings).length > 0) {
      // use this to select inputEl and change value
      for (const [key, data] of Object.entries(settings)) {
        //change format to match id
        const value = data["value"];
        const method = setMethodUI ? "ui" : data["method"];
        const global = data["global"];
        try {
          // get only inputs without attribute data-is-multiple
          const inps = this.container.querySelectorAll(
            `[name='${key}']:not([data-is-multiple])`,
          );

          inps.forEach((inp) => {
            //form related values are excludes
            const inpName = inp.getAttribute("name");

            if (this.isAvoidInpList("input", inp, inpName, this.container))
              return;

            //SET DISABLED / ENABLED
            //for regular input
            this.setCheckbox(inp, method, value);
            this.setInput(inp, method, value);

            //for select
            if (inp.tagName === "SELECT") {
              inp.parentElement
                .querySelector(
                  `button[data-setting-select-dropdown-btn][value='${value}']`,
                )
                .click();
              inp.setAttribute("data-method", method);
            }

            if (forceEnabled) {
              inp.removeAttribute("disabled");
            } else {
              if (method === "ui" || method === "default") {
                inp.removeAttribute("disabled");
              } else {
                inp.setAttribute("disabled", "");
              }

              if (global) inp.removeAttribute("disabled");
            }
          });
        } catch (err) {}
      }
    }
  }

  removePrevMultiples() {
    const multiPlugins = this.container.querySelectorAll(
      `[data-${this.prefix}-settings-multiple]`,
    );
    multiPlugins.forEach((multiGrp) => {
      if (
        !multiGrp
          .getAttribute(`data-${this.prefix}-settings-multiple`)
          .includes("SCHEMA")
      )
        multiGrp.remove();
    });
  }

  setMultipleInps(settings) {
    //remove all multiples
    this.removePrevMultiples();
    //keep only multiple settings value
    const multipleSettings = this.getMultiplesOnly(settings);
    const sortMultiples =
      this.sortMultipleByContainerAndSuffixe(multipleSettings);

    // Need to set method as ui if clone
    const isClone = this.currAction === "clone" ? true : false;
    this.setMultipleToDOM(sortMultiples, isClone);
    // Show at least one mult group
    this.addOneMultGroup();
  }

  getMultiplesOnly(settings) {
    //get schema settings
    const multiples = {};

    const schemaSettings = this.container.querySelectorAll(
      `[data-setting-container$="SCHEMA"]`,
    );

    // loop on every schema settings
    schemaSettings.forEach((schema) => {
      const schemaName = schema
        .getAttribute("data-setting-container")
        .replace("_SCHEMA", "")
        .trim();

      //check if match with service setting
      for (const [key, data] of Object.entries(settings)) {
        if (key.includes(schemaName)) {
          multiples[key] = {
            value: data["value"],
            method: data["method"],
            global: data["global"],
          };
        }
      }
    });
    return multiples;
  }

  addOneMultGroup() {
    const multAddBtns = this.container.querySelectorAll(
      `[data-${this.prefix}-multiple-add]`,
    );
    console.log("mult groups, ", multAddBtns);
    multAddBtns.forEach((btn) => {
      const att = btn.getAttribute(`data-${this.prefix}-multiple-add`);
      //check if already one (SCHEMA exclude so length >= 2)
      const multGroups = this.container.querySelectorAll(
        `[data-${this.prefix}-settings-multiple^="${att}"]`,
      );
      if (multGroups.length >= 2) return;

      btn.click();
    });
  }

  getInpsToCheckByMode() {
    // For advanced, we want to check all inputs
    // For simple, we want to check only current step inputs to continue

    const inps =
      this.mode === "simple"
        ? this.container.querySelectorAll(
            "[data-step]:not(.hidden) input[data-setting-input]",
          )
        : this.container.querySelectorAll(
            "[data-plugin-item]:not(.hidden) input[data-setting-input], [data-plugin-item][class*='hidden'] input[data-setting-input]",
          );
    return inps;
  }

  checkVisibleInpsValidity() {
    try {
      const inps = this.getInpsToCheckByMode();
      // merge input with visible and not visible
      if (inps.length <= 0) return;

      let isAllValid = true;
      let invalidInpName = "";
      let invalidInp = null;

      for (let i = 0; i < inps.length; i++) {
        // for all inputs
        if (!inps[i].validity.valid) {
          invalidInp = inps[i];
          isAllValid = false;
          invalidInpName = inps[i].getAttribute("name");
          break;
        }

        // special case for SERVER_NAME
        if (
          inps[i].getAttribute("name") === "SERVER_NAME" &&
          inps[i].value !== ""
        ) {
          // Case conflict with another server name
          const serverNames = document.querySelectorAll(
            "[data-services-service]",
          );
          const serverNameValue = inps[i].getAttribute("value");
          serverNames.forEach((serverName) => {
            const name = serverName.getAttribute("data-services-service");
            if (name === serverNameValue) return;
            if (name === inps[i].value) {
              invalidInpName = inps[i]?.getAttribute("name");
              isAllValid = false;
            }
          });
        }
      }

      const errMsg = form.querySelector("[data-services-modal-error-msg]");
      if (!isAllValid) {
        invalidInp.classList.add("invalid");
        const invalidEl = invalidInp
          .closest("form")
          .querySelector(`[data-invalid=${invalidInp.getAttribute("id")}]`);
        invalidEl.classList.remove("hidden", "md:hidden");
        // Wait a little that modal is fully open to focus on invalid input, because not working when element is hidden
        setTimeout(() => {
          // only focus  if not another input is focus
          if (document.activeElement.tagName !== "INPUT") invalidInp.focus();
        }, 30);

        errMsg.textContent = `${invalidInpName} must be valid to submit`;
        errMsg.classList.remove("hidden");
        formMode == "simple" ? this.nextBtn.setAttribute("disabled", "") : null;
        formMode == "advanced"
          ? form
              .querySelector("button[data-services-modal-submit]")
              .setAttribute("disabled", "")
          : null;
      }

      if (isAllValid) {
        errMsg.classList.add("hidden");
        formMode == "simple" ? this.nextBtn.removeAttribute("disabled") : null;
        formMode == "advanced"
          ? form
              .querySelector("button[data-services-modal-submit]")
              .removeAttribute("disabled")
          : null;
      }
    } catch (e) {}
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
      const relateSetting = this.container.querySelector(
        `[data-setting-container=${nameSuffixLess}_SCHEMA]`,
      );
      if (!relateSetting) continue;
      const relateCtnr = relateSetting.closest(
        `[data-${this.prefix}-settings-multiple]`,
      );
      const relateCtnrName = relateCtnr.getAttribute(
        `data-${this.prefix}-settings-multiple`,
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

  //put multiple on the right plugin, on schema container
  setMultipleToDOM(sortMultObj) {
    //we loop on each multiple that contains values to render to DOM
    for (const [schemaCtnrName, multGroupBySuffix] of Object.entries(
      sortMultObj,
    )) {
      //we need to access the DOM schema container
      const schemaCtnr = this.container.querySelector(
        `[data-${this.prefix}-settings-multiple="${schemaCtnrName}"]`,
      );

      //now we have to loop on each multiple settings group
      for (const [suffix, settings] of Object.entries(multGroupBySuffix)) {
        //we have to clone schema container first
        const schemaCtnrClone = schemaCtnr.cloneNode(true);
        //remove id to avoid duplicate and for W3C
        schemaCtnr.removeAttribute("id");
        //now we replace _SCHEMA by current suffix everywhere we need
        //unless it is 0 that means no suffix
        const suffixFormat = +suffix === 0 ? `` : `_${suffix}`;
        this.changeCloneSuffix(schemaCtnrClone, suffixFormat);
        //then we have to loop on every settings of current group to change clone values by right ones
        for (const [name, data] of Object.entries(settings)) {
          //get setting container of clone container
          const settingContainer = schemaCtnrClone.querySelector(
            `[data-setting-container="${name}"]`,
          );
          //replace input info and disabled state
          this.setSettingsByAtt(
            settingContainer,
            data["method"],
            data["value"],
          );
        }
        //send schema clone to DOM and show it
        this.showClone(schemaCtnr, schemaCtnrClone);
      }
    }
  }

  changeCloneSuffix(schemaCtnrClone, suffix) {
    //rename multiple container
    schemaCtnrClone.setAttribute(
      `data-${this.prefix}-settings-multiple`,
      schemaCtnrClone
        .getAttribute(`data-${this.prefix}-settings-multiple`)
        .replace("_SCHEMA", suffix),
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
      "[data-setting-container]",
    );
    settingCtnrs.forEach((settingCtnr) => {
      settingCtnr.setAttribute(
        "data-setting-container",
        settingCtnr
          .getAttribute("data-setting-container")
          .replace("_SCHEMA", suffix),
      );
      settingCtnr.setAttribute(
        "id",
        settingCtnr.getAttribute("id").replace("_SCHEMA", suffix),
      );
    });

    // rename label
    const labelEls = schemaCtnrClone.querySelectorAll("label");
    labelEls.forEach((label) => {
      label.setAttribute(
        "for",
        label.getAttribute("for").replace("_SCHEMA", suffix),
      );
    });

    //rename popover
    const popoverBtns = schemaCtnrClone.querySelectorAll("[data-popover-btn]");
    popoverBtns.forEach((popoverBtn) => {
      popoverBtn.setAttribute(
        "data-popover-btn",
        popoverBtn.getAttribute("data-popover-btn").replace("_SCHEMA", suffix),
      );
    });

    const popoverContents = schemaCtnrClone.querySelectorAll(
      "[data-popover-content]",
    );
    popoverContents.forEach((popoverContent) => {
      popoverContent.setAttribute(
        "data-popover-content",
        popoverContent
          .getAttribute("data-popover-content")
          .replace("_SCHEMA", suffix),
      );
    });

    //rename invalid
    const invalidEls = schemaCtnrClone.querySelectorAll("[data-invalid]");
    invalidEls.forEach((invalidEl) => {
      invalidEl.setAttribute(
        "data-invalid",
        invalidEl.getAttribute("data-invalid").replace("_SCHEMA", suffix),
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

  showClone(schemaCtnr, schemaCtnrClone) {
    schemaCtnr.insertAdjacentElement("afterend", schemaCtnrClone);
    schemaCtnrClone.classList.remove("hidden");
    schemaCtnrClone.classList.add("grid");
  }

  hiddenIfNoMultiples() {
    //hide multiple btn if no multiple exist on a plugin
    const multiples = this.container.querySelectorAll(
      `[data-${this.prefix}-settings-multiple]`,
    );
    multiples.forEach((container) => {
      if (container.querySelectorAll(`[data-setting-container]`).length <= 0)
        container.parentElement
          .querySelector("[data-multiple-handler]")
          .classList.add("hidden");
    });
  }

  showMultByAtt(att) {
    const multContainers = this.container.querySelectorAll(
      `[data-${this.prefix}-settings-multiple^=${att}]`,
    );
    multContainers.forEach((container) => {
      if (
        !container
          .getAttribute(`data-${this.prefix}-settings-multiple`)
          .includes("SCHEMA")
      )
        container.classList.remove("hidden");
    });
  }

  toggleMultByAtt(att) {
    const multContainers = this.container.querySelectorAll(
      `[data-${this.prefix}-settings-multiple^=${att}]`,
    );
    multContainers.forEach((container) => {
      if (
        !container
          .getAttribute(`data-${this.prefix}-settings-multiple`)
          .includes("SCHEMA")
      )
        container.classList.toggle("hidden");
    });
  }

  //global value isn't check at this point
  setDisabledMultNew(container) {
    const settings = container.querySelectorAll("[data-setting-container]");

    settings.forEach((setting) => {
      //replace input info
      try {
        const inps = setting.querySelectorAll("input");
        inps.forEach((inp) => {
          const method = inp.getAttribute("data-default-method");
          if (method === "ui" || method === "default") {
            inp.removeAttribute("disabled");
          } else {
            inp.setAttribute("disabled", "");
          }
        });
      } catch (err) {}
      //or select
      try {
        const selects = setting.querySelectorAll("select");
        selects.forEach((select) => {
          const method = select.getAttribute("data-default-method");
          const name = select.getAttribute(
            `data-${this.prefix}-setting-select-default`,
          );
          const selDOM = this.container.querySelector(
            `button[data-${this.prefix}-setting-select='${name}']`,
          );
          if (method === "ui" || method === "default") {
            selDOM.removeAttribute("disabled", "");
          } else {
            selDOM.setAttribute("disabled", "");
          }
        });
      } catch (err) {}
    });
  }

  getSuffixNumOrFalse(name) {
    const num = !isNaN(Number(name.substring(name.lastIndexOf("_") + 1)))
      ? Number(name.substring(name.lastIndexOf("_") + 1))
      : "";
    return num;
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
    this.switchModeBtn.addEventListener("click", () => {
      const currMode = this.switchModeBtn.getAttribute(
        "data-toggle-settings-mode-btn",
      );
      const switchMode = currMode === "advanced" ? "simple" : "advanced";
      this.switchMode(switchMode);
    });

    this.modal.addEventListener("click", (e) => {
      //close
      try {
        if (
          e.target.closest("button").hasAttribute("data-services-modal-close")
        ) {
          this.closeModal();
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
    if (action === "new") {
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

const settings = new Settings(
  document.querySelector("[data-advanced][data-services-modal-form]"),
  "advanced",
);
// const setAdvancedMultiple = new MultipleActions("services", document.querySelector("[data-advanced][data-services-modal-form]"));

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
