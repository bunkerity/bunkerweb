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

// Hide completely configs card in all plugins hidden
document
  .querySelector("input#settings-filter")
  .addEventListener("input", () => {
    console.log("input");
    const tabs = document
      .querySelector("[data-global-config-tabs-desktop]")
      .querySelectorAll("[data-tab-handler]");
    let isAllHidden = true;
    for (let i = 0; i < tabs.length; i++) {
      const plugin = tabs[i];
      if (!plugin.classList.contains("hidden")) {
        console.log(plugin);
        isAllHidden = false;
        break;
      }
    }

    const formEl = document.querySelector("[data-global-config-form]");
    const noMatchEl = document.querySelector("[data-global-config-nomatch]");

    if (isAllHidden) {
      noMatchEl.classList.remove("hidden");
      formEl.classList.add("hidden");
    }

    if (!isAllHidden) {
      formEl.classList.remove("hidden");
      noMatchEl.classList.add("hidden");
    }
  });
