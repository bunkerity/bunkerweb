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
const setTabs = new Tabs(
  document.querySelector("[data-global-config-tabs-container]"),
  document.querySelector("[data-global-config-plugins-container]"),
);
const format = new FormatValue();
const setMultiple = new Multiple("global-config");

const setFilterGlobal = new FilterSettings(
  "keyword",
  document.querySelector("[data-global-config-tabs-container]"),
  document.querySelector("[data-global-config-plugins-container]"),
);

const checkServiceModalKeyword = new CheckNoMatchFilter(
  document.querySelector("input#keyword"),
  "input",
  document
    .querySelector("[data-global-config-plugins-container]")
    .querySelectorAll("[data-plugin-item]"),
  document.querySelector("[data-global-config-form]"),
  document.querySelector("[data-global-config-nomatch]"),
);
