import { Checkbox, Select, Password } from "./utils/form.js";
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
      `[${this.prefix}-settings-multiple]`
    );
    multiples.forEach((container) => {
      if (container.querySelectorAll(`[setting-container]`).length <= 0)
        container.parentElement
          .querySelector("[multiple-handler]")
          .classList.add("hidden");
    });
  }
}

const setCheckbox = new Checkbox();
const setSelect = new Select();
const setPassword = new Password();

const setPopover = new Popover("main", "global-config");
const setTabs = new Tabs("[global-config-tabs]", "global-config");
const format = new FormatValue();
const setMultiple = new Multiple("global-config");
const setFilterGlobal = new FilterSettings(
  "settings-filter",
  "[service-content='settings']"
);
