
class Settings {
    constructor(mode, formEl, prefix = "services") {
      this.prefix = prefix;
        this.container = formEl;
        this.mode=mode;

        this.serverNameInps = this.container.querySelectorAll(
        'input[name="SERVER_NAME"][data-setting-input]',
        );

        this.submitBtn = this.container.querySelector(
        `button[data-${this.prefix}-modal-submit]`,
        );
      this.currAction = "";
      this.currMethod = "";
      this.oldServName = "";
        this.initSettings();
    }

    initSettings() {
        window.addEventListener("DOMContentLoaded", () => {
            this.container.addEventListener("input", (e) => {
              this.checkVisibleInpsValidity();
            });
          });
    }
  
    resetServerName() {
      this.serverNameInps.forEach((inpServName) => {
        inpServName.getAttribute("value", "");
        inpServName.removeAttribute("disabled", "");
        inpServName.value = "";
      });
    }
  
    isAvoidInpList(type, inp, inpName) {
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
      const oldNameInps = this.container.querySelectorAll(
        'input[name="OLD_SERVER_NAME"]',
      );
  
      oldNameInps.forEach((inp) => {
        inp.setAttribute("value", this.oldServName);
        inp.value = this.oldServName;
      });
    }
  
    updateOperation() {
      // update operation and other hidden inputs for all mode in modal
      const operationInps = this.container.querySelectorAll(
        'input[name="operation"]',
      );
      operationInps.forEach((inp) => {
        inp.setAttribute("value", this.operation);
        inp.value = this.operation;
      });
    }
  
    updateData(
      action,
      oldServName,
      operation
    ) {
      // Get global needed data
      this.currAction = action;
      this.oldServName = oldServName;
    this.operation = operation;
      this.updateOperation(operation);
      this.updateOldNameValue();
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

  }

  
class SettingsSimple {
  constructor() {

    this.nextBtn = this.container.querySelector("button[data-simple-next]");
    this.backBtn = this.container.querySelector("button[data-simple-back]");

    this.initSimple();
  }

  initSimple() {
    // TODO :       handle this.changeSubmitBtn();

   
    // SIMPLE MODE ACTIONS
      this.nextBtn.addEventListener("click", () => {
        this.nextSimpleStep();
      });

      this.backBtn.addEventListener("click", () => {
        this.prevSimpleStep();
      });
  }

  resetSimpleMode() {
    // reset button
    this.backBtn.setAttribute("disabled", "");
    this.nextBtn.removeAttribute("disabled");
    // hidden all steps and show first one
    const steps = this.container.querySelectorAll("[data-step]");
    steps.forEach((step) => {
      step.classList.add("hidden");
    });
    const firstStep = this.container.querySelector("[data-step='1']");
    firstStep.classList.remove("hidden");
    this.updateSimpleActions();
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
      this.submitBtn.classList.add("hidden");
    }

    if (!nextStep) {
      this.nextBtn.classList.add("hidden");
      this.submitBtn.classList.remove("hidden");
    }

    if (prevStep) {
      this.backBtn.removeAttribute("disabled");
    }

    if (!prevStep) {
      this.backBtn.setAttribute("disabled", "");
    }
  }

}

class SettingsSwitch {
constructor(switchBtn, settingsForms, prefix = "services") {
  this.prefix = prefix;
  this.switchModeBtn = switchBtn;
  // dict with mode as key and form element as value
  this.settingsForms = settingsForms;

  this.init();
}

init() {
    this.switchModeBtn.addEventListener("click", () => {
      setTimeout(() => {
        this.checkVisibleInpsValidity();
      }, 20);
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

}

class SettingsMultiple {
  constructor() {
    this.multSettingsName = JSON.parse(
      document
        .querySelector("input[data-plugins-multiple]")
        .getAttribute("data-plugins-multiple")
        .replaceAll(`'`, `"`),
    );
   
    this.initMultiple();
  }

  initMultiple() {
    window.addEventListener("load", () => {
      this.hiddenIfNoMultiples();
    });
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


class SettingsAdvanced {
constructor(settingsFilterEl = null) {
  this.settingsFilterEl = settingsFilterEl;  
}

setSettingsAdvanced(
  settingsJSON,
  setMethodUI = false,
  forceEnabled = false,
  emptyServerName = false,
) {
  const settings = JSON.parse(settingsJSON);
  this.setRegularInps(settings, forceEnabled, setMethodUI, emptyServerName);
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


resetFilterInp() {
  if(this.settingsFilterEl) {
  const inpFilter = document.querySelector('input[name="settings-filter"]');
  inpFilter.value = "";
  inpFilter.dispatchEvent(new Event("input"));
  }
}
}
