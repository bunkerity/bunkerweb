import { Checkbox, Select, Password, DisabledPop } from "./utils/form.js";
import {
  Popover,
  Tabs,
  FormatValue,
  FilterSettings,
} from "./utils/settings.js";

class Multiple {
  constructor(prefix) {
    this.prefix = prefix;
    this.init();
  }
  //hide multiples handler if no multiple setting on plugin
  init() {
    //hide multiple btn if no multiple exist on a plugin
    const multiples = document.querySelectorAll(
      `[data-${this.prefix}-settings-multiple]`
    );
    multiples.forEach((container) => {
      if (container.querySelectorAll(`[data-setting-container]`).length <= 0)
        container.parentElement
          .querySelector("[data-multiple-handler]")
          .classList.add("hidden");
    });
  }
}

const setCheckbox = new Checkbox();
const setSelect = new Select();
const setPassword = new Password();
const setDisabledPop = new DisabledPop();

const setPopover = new Popover("main", "global-config");
const setTabs = new Tabs("[global-config-tabs]", "global-config");
const format = new FormatValue();
const setMultiple = new Multiple("global-config");
const setFilterGlobal = new FilterSettings(
  "settings-filter",
  "[data-service-content='settings']"
);
