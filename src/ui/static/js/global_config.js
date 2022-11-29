import { Checkbox, Select } from "./utils/form.js";
import { Popover, Tabs, FormatValue } from "./utils/settings.js";

class FilterSettings {
  constructor(prefix) {
    this.prefix = prefix;
    this.input = document.querySelector("input#settings-filter");
    //DESKTOP
    this.deskTabs = document.querySelectorAll(`[${this.prefix}-item-handler]`);
    this.init();
  }

  init() {
    this.input.addEventListener("input", () => {
      this.resetFilter();
      //get inp format
      const inpValue = this.input.value.trim().toLowerCase();
      //loop all tabs
      this.deskTabs.forEach((tab) => {
        //get settings of tabs except multiples
        const settings = this.getSettingsFromTab(tab);

        //compare total count to currCount to determine
        //if tabs need to be hidden
        const settingCount = settings.length;
        let hiddenCount = 0;
        settings.forEach((setting) => {
          try {
            const title = setting
              .querySelector("h5")
              .textContent.trim()
              .toLowerCase();
            if (!title.includes(inpValue)) {
              setting.classList.add("hidden");
              hiddenCount++;
            }
          } catch (err) {}
        });
        //case no setting match, hidden tab and content
        if (settingCount === hiddenCount) {
          const tabName = tab.getAttribute(`${this.prefix}-item-handler`);
          //hide mobile and desk tabs
          tab.classList.add("hidden");
          document
            .querySelector(`[${this.prefix}-mobile-item-handler="${tabName}"]`)
            .classList.add("hidden");
          document
            .querySelector(`[${this.prefix}-item=${tabName}]`)
            .querySelector("[setting-header]")

            .classList.add("hidden");
        }
      });
    });
  }

  resetFilter() {
    this.deskTabs.forEach((tab) => {
      const tabName = tab.getAttribute(`${this.prefix}-item-handler`);
      //hide mobile and desk tabs
      tab.classList.remove("hidden");
      document
        .querySelector(`[${this.prefix}-mobile-item-handler="${tabName}"]`)
        .classList.remove("hidden");
      document
        .querySelector(`[${this.prefix}-item=${tabName}]`)
        .querySelector("[setting-header]")
        .classList.remove("hidden");
      const settings = this.getSettingsFromTab(tab);
      settings.forEach((setting) => {
        setting.classList.remove("hidden");
      });
    });
  }

  getSettingsFromTab(tabEl) {
    const tabName = tabEl.getAttribute(`${this.prefix}-item-handler`);
    const settingContainer = document
      .querySelector(`[${this.prefix}-item="${tabName}"]`)
      .querySelector(`[${this.prefix}-settings]`);
    const settings = settingContainer.querySelectorAll("[setting-container]");
    return settings;
  }
}

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

const setCheckbox = new Checkbox("[global-config-form]");
const setSelect = new Select("[global-config-form]", "global-config");
const setPopover = new Popover("main", "global-config");
const setTabs = new Tabs("[global-config-tabs]", "global-config");
const format = new FormatValue();
const setMultiple = new Multiple("global-config");
const setFilter = new FilterSettings("global-config");
