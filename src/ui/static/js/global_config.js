import {
  Popover,
  Tabs,
  FormatValue,
  FilterSettings,
  CheckNoMatchFilter,
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
      `[data-${this.prefix}-settings-multiple]`,
    );
    multiples.forEach((container) => {
      if (container.querySelectorAll(`[data-setting-container]`).length <= 0)
        container.parentElement
          .querySelector("[data-multiple-handler]")
          .classList.add("hidden");
    });
  }
}

const setPopover = new Popover("main", "global-config");
const setTabs = new Tabs("[global-config-tabs]", "global-config");
const format = new FormatValue();
const setMultiple = new Multiple("global-config");
const setFilterGlobal = new FilterSettings(
  "settings-filter",
  "[data-service-content='settings']",
);

const checkServiceModalKeyword = new CheckNoMatchFilter(
  document.querySelector("input#settings-filter"),
  "input",
  document
    .querySelector("[data-global-config-tabs]")
    .querySelectorAll("[data-tab-handler]"),
  document.querySelector("[data-global-config-form]"),
  document.querySelector("[data-global-config-nomatch]"),
);
