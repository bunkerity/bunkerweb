import {
  Popover,
  TabsSelect,
  FormatValue,
  FilterSettings,
  CheckNoMatchFilter,
  showInvalid,
} from "./utils/settings.js";

import { Dropdown } from "./utils/dashboard.js";

class Multiple {
  constructor(prefix) {
    this.prefix = prefix;
    this.container = document.querySelector("main");
    this.init();
  }

  init() {
    window.addEventListener("load", () => {
      this.hiddenIfNoMultiples();

      try {
        //remove all multiples
        this.removePrevMultiples();
        //get multiple service values and parse as obj
        const globalConfigSettings = document
          .querySelector(`[data-${this.prefix}-settings]`)
          .getAttribute("data-value");
        const obj = JSON.parse(globalConfigSettings);
        //keep only multiple settings value
        const multipleSettings = this.getMultiplesOnly(obj);
        const sortMultiples =
          this.sortMultipleByContainerAndSuffixe(multipleSettings);
        this.setMultipleToDOM(sortMultiples);
      } catch (err) {}
    });

    document
      .querySelector(`[data-${this.prefix}-form]`)
      .addEventListener("click", (e) => {
        //ADD BTN
        try {
          if (
            e.target
              .closest("button")
              .hasAttribute(`data-${this.prefix}-multiple-add`)
          ) {
            if (this.isAvoidAction(e.target)) return;

            //get plugin from btn
            const btn = e.target.closest("button");
            const attName = btn.getAttribute(
              `data-${this.prefix}-multiple-add`,
            );
            //get all multiple groups
            const multipleEls = document.querySelectorAll(
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
            const schema = document.querySelector(
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
            if (this.isAvoidAction(e.target)) return;
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
            if (this.isAvoidAction(e.target)) return;

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
                  const dropdown = document.querySelector(
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

  isAvoidAction(target) {
    // check that not disabled pro plugin
    const proDisabled = target
      .closest("[data-plugin-item]")
      .hasAttribute("data-pro-disabled")
      ? true
      : false;

    return proDisabled;
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
        `[data-setting-container=${nameSuffixLess}_SCHEMA]`,
      );
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

  addOneMultGroup() {
    const settings = document.querySelector(`[data-${this.prefix}-modal-form]`);
    const multAddBtns = settings.querySelectorAll(
      `[data-${this.prefix}-multiple-add]`,
    );
    multAddBtns.forEach((btn) => {
      //check if already one (SCHEMA exclude so length >= 2)
      const plugin = btn.closest("[data-plugin-item]");
      if (
        plugin.querySelectorAll(`[data-${this.prefix}-settings-multiple]`)
          .length >= 2
      )
        return;
      btn.click();
    });
  }

  showMultByAtt(att) {
    const multContainers = document.querySelectorAll(
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
    const multContainers = document.querySelectorAll(
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

  getMultiplesOnly(settings) {
    //get schema settings
    const multiples = {};
    const schemaSettings = document.querySelectorAll(
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

  //put multiple on the right plugin, on schema container
  setMultipleToDOM(sortMultObj) {
    //we loop on each multiple that contains values to render to DOM
    for (const [schemaCtnrName, multGroupBySuffix] of Object.entries(
      sortMultObj,
    )) {
      //we need to access the DOM schema container
      const schemaCtnr = document.querySelector(
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
          this.setSetting(
            data["value"],
            data["method"],
            data["global"],
            settingContainer,
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

  setSetting(value, method, global, settingContainer) {
    //update input
    try {
      const inps = settingContainer.querySelectorAll("input");
      inps.forEach((inp) => {
        //form related values are excludes
        const inpName = inp.getAttribute("name");
        if (
          inpName === "csrf_token" ||
          inpName === "OLD_SERVER_NAME" ||
          inpName === "is_draft" ||
          inpName === "operation" ||
          inpName === "settings-filter"
        )
          return;

        //for settings input
        if (inp.getAttribute("type") === "checkbox") {
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

        if (inp.getAttribute("type") !== "checkbox") {
          inp.setAttribute("value", value);
          inp.value = value;
          inp.setAttribute("data-method", method);
        }
        this.setDisabledMultServ(inp, method, global);
      });
    } catch (err) {}
    //update select
    try {
      const select = settingContainer.querySelector("select");
      select.setAttribute("data-method", method);

      //click the custom select dropdown btn value to update select value
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

      this.setDisabledMultServ(btnCustom, method, global);
    } catch (err) {}
  }

  showClone(schemaCtnr, schemaCtnrClone) {
    schemaCtnr.insertAdjacentElement("afterend", schemaCtnrClone);
    schemaCtnrClone.classList.remove("hidden");
    schemaCtnrClone.classList.add("grid");
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
          const selDOM = document.querySelector(
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

  //for already existing global config multiples
  //global is check
  setDisabledMultServ(inp, method, global) {
    // Check if pro
    const proDisabled = inp
      .closest("[data-plugin-item]")
      .hasAttribute("data-pro-disabled")
      ? true
      : false;
    if (proDisabled) return inp.setAttribute("disabled", "");
    if (global) return inp.removeAttribute("disabled");

    if (method === "ui" || method === "default") {
      inp.removeAttribute("disabled");
    } else {
      inp.setAttribute("disabled", "");
    }
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
      `[data-${this.prefix}-settings-multiple]`,
    );
    multiples.forEach((container) => {
      if (container.querySelectorAll(`[data-setting-container]`).length <= 0)
        container.parentElement
          .querySelector("[data-multiple-handler]")
          .classList.add("hidden");
    });
  }

  removePrevMultiples() {
    const multiPlugins = document.querySelectorAll(
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

const setPopover = new Popover("main", "global-config");
const setDrop = new Dropdown("global-config");
const setTabsSelect = new TabsSelect(
  document.querySelector("[data-global-config-tabs-select-container]"),
  document.querySelector("[data-global-config-plugins-container]"),
);
const setInvalid = new showInvalid();
const format = new FormatValue();

const setFilterGlobal = new FilterSettings(
  "keyword",
  document.querySelector("[data-global-config-tabs-select-container]"),
  document.querySelector("[data-global-config-plugins-container]"),
);

const setMultiple = new Multiple("global-config");

const checkServiceModalKeyword = new CheckNoMatchFilter(
  document.querySelector("input#keyword"),
  "input",
  document
    .querySelector("[data-global-config-plugins-container]")
    .querySelectorAll("[data-plugin-item]"),
  document.querySelector("[data-global-config-form]"),
  document.querySelector("[data-global-config-nomatch]"),
);

try {
  const checkServiceCardSelect = new CheckNoMatchFilter(
    document.querySelectorAll(
      "button[data-global-config-setting-select-dropdown-btn]",
    ),
    "select",
    document
      .querySelector("[data-global-config-plugins-container]")
      .querySelectorAll("[data-plugin-item]"),
    document.querySelector("[data-global-config-form]"),
    document.querySelector("[data-global-config-nomatch]"),
  );
} catch (e) {}
