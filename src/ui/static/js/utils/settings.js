class Popover {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("pointerover", (e) => {
      //POPOVER LOGIC
      try {
        if (
          e.target.closest("button").hasAttribute(`data-popover-btn`) ||
          e.target.closest("svg").hasAttribute(`data-popover-btn`)
        ) {
          this.showPopover(e.target);
        }
      } catch (err) {}
    });

    window.addEventListener("pointerout", (e) => {
      //POPOVER LOGIC
      try {
        if (
          e.target.closest("button").hasAttribute(`data-popover-btn`) ||
          e.target.closest("svg").hasAttribute(`data-popover-btn`)
        ) {
          this.hidePopover(e.target);
        }
      } catch (err) {}
    });
  }

  showPopover(el) {
    const btn = el.closest("button").hasAttribute("data-popover-btn")
      ? el.closest("button")
      : el.closest("svg");
    const popoverName = btn.getAttribute("data-popover-btn");
    //toggle curr popover
    const popover = btn.parentElement.querySelector(
      `[data-popover-content=${popoverName}]`,
    );
    popover.classList.add("transition-all", "delay-200", "opacity-0");
    popover.classList.remove("hidden");
    setTimeout(() => {
      popover.classList.remove("opacity-0");
    }, 10);
  }

  hidePopover(el) {
    const btn = el.closest("button").hasAttribute("data-popover-btn")
      ? el.closest("button")
      : el.closest("svg");
    const popoverName = btn.getAttribute("data-popover-btn");
    //toggle curr popover
    const popover = btn.parentElement.querySelector(
      `[data-popover-content=${popoverName}]`,
    );
    popover.classList.add("hidden");
    popover.classList.remove("transition-all", "delay-200");
  }
}

class TabsSelect {
  constructor(tabContainer, contentContainer) {
    this.tabContainer = tabContainer;
    this.contentContainer = contentContainer;
    this.tabArrow = tabContainer
      .querySelector("[data-tab-select-dropdown-btn]")
      .querySelector("[data-tab-select-dropdown-arrow]");
    this.init();
  }

  init() {
    window.addEventListener("click", (e) => {
      try {
        if (
          e.target.closest("button").hasAttribute("data-tab-select-handler")
        ) {
          //get needed data
          const tab = e.target.closest("button");
          const tabAtt = tab.getAttribute("data-tab-select-handler");
          const text = tab.textContent;
          // change style
          this.resetTabsStyle();
          this.highlightClicked(tabAtt);
          //show content
          this.hideAllSettings();
          this.showSettingClicked(tabAtt);
          //close dropdown and change btn textcontent on mobile
          this.setDropBtnText(tabAtt, text);
          this.closeDropdown();
          // Change URL fragment
          if (window.location.pathname.endsWith("global_config")) {
            window.history.replaceState(
              null,
              "",
              `${window.location.pathname}#${tabAtt}`,
            );
          }
        }
      } catch (e) {}

      try {
        if (
          e.target
            .closest("button")
            .hasAttribute("data-tab-select-dropdown-btn")
        ) {
          this.toggleDropdown();
        }
      } catch (err) {}
    });

    // If fragment exists, click on the corresponding tab
    if (
      window.location.hash &&
      window.location.pathname.endsWith("global_config")
    ) {
      const fragment = window.location.hash.substring(1);
      if (fragment) {
        const tab = this.tabContainer.querySelector(
          `button[data-tab-select-handler='${fragment}']`,
        );
        tab.click();
        // Scroll to the top of the page (with a delay to ensure the tab is clicked first)
        setTimeout(() => {
          window.scrollTo(0, 0);
        }, 100);
      }
    }
  }

  resetTabsStyle() {
    const tabsEl = this.tabContainer.querySelectorAll(
      "button[data-tab-select-handler]",
    );
    tabsEl.forEach((tab) => {
      tab.classList.remove("active");
    });
  }

  highlightClicked(tabAtt) {
    const tabMobile = this.tabContainer.querySelector(
      `button[data-tab-select-handler='${tabAtt}']`,
    );
    tabMobile.classList.add("active");
  }

  hideAllSettings() {
    const plugins =
      this.contentContainer.querySelectorAll("[data-plugin-item]");
    plugins.forEach((plugin) => {
      plugin.classList.add("hidden");
    });
  }

  showSettingClicked(tabAtt) {
    const plugin = this.contentContainer.querySelector(
      `[data-plugin-item='${tabAtt}']`,
    );
    plugin.classList.remove("hidden");
  }

  setDropBtnText(tabAtt, text) {
    const dropBtn = this.tabContainer.querySelector(
      "[data-tab-select-dropdown-btn]",
    );
    dropBtn.setAttribute("data-tab-id", tabAtt);
    dropBtn.querySelector("span").textContent = text;
  }

  closeDropdown() {
    const dropdown = this.tabContainer.querySelector(
      "[data-tab-select-dropdown]",
    );
    dropdown.classList.add("hidden");
    dropdown.classList.remove("flex");

    this.updateTabArrow();
  }

  toggleDropdown() {
    const dropdown = this.tabContainer.querySelector(
      "[data-tab-select-dropdown]",
    );
    dropdown.classList.toggle("hidden");
    dropdown.classList.toggle("flex");

    this.updateTabArrow();
  }

  updateTabArrow() {
    const dropdown = this.tabContainer.querySelector(
      "[data-tab-select-dropdown]",
    );

    if (dropdown.classList.contains("hidden")) {
      this.tabArrow.classList.remove("rotate-180");
    }

    if (dropdown.classList.contains("flex")) {
      this.tabArrow.classList.add("rotate-180");
    }
  }
}

class FormatValue {
  constructor() {
    this.inputs = document.querySelectorAll("input");
    this.init();
  }

  init() {
    this.inputs.forEach((inp) => {
      try {
        inp.setAttribute("value", inp.getAttribute("value").trim());
        inp.value = inp.value.trim();
      } catch (err) {}
    });
  }
}

class FilterSettings {
  constructor(
    inputID,
    tabContainer,
    contentContainer,
    prefix = "global-config",
  ) {
    this.input = document.querySelector(`input#${inputID}`);
    this.prefix = prefix;
    this.contextTxtEl = document.querySelector(
      `span[data-${this.prefix}-setting-select-text="context"]`,
    );
    this.tabContainer = tabContainer;
    this.contentContainer = contentContainer;
    this.tabsEls = this.tabContainer.querySelectorAll(
      `[data-tab-select-handler]`,
    );

    this.init();
  }

  init() {
    window.addEventListener("DOMContentLoaded", () => {
      if (this.input) {
        this.input.addEventListener("input", () => {
          this.runFilter();
        });
      }

      window.addEventListener("click", (e) => {
        try {
          if (
            e.target.hasAttribute(
              "data-global-config-setting-select-dropdown-btn",
            ) &&
            e.target.getAttribute(
              "data-global-config-setting-select-dropdown-btn",
            ) === "context"
          ) {
            return this.runFilter();
          }
        } catch (e) {}
      });
    });
  }

  runFilter() {
    this.resetFilter();
    //get inp format
    const inpValue = this.input.value.trim().toLowerCase();

    //loop all tabs
    this.tabsEls.forEach((tab) => {
      const tabName = tab.getAttribute(`data-tab-select-handler`);
      //get settings of tabs except multiples
      const settings = this.getSettingsFromTab(tab);

      //compare total count to currCount to determine
      //if tabs need to be hidden
      const settingCount = settings.length;
      let settingHiddenCount = 0;
      settings.forEach((setting) => {
        try {
          let needToHide = false;
          const title = setting
            .querySelector("h5")
            .textContent.trim()
            .toLowerCase();
          if (!title.includes(inpValue) && inpValue !== "") {
            needToHide = true;
          }

          // check context if filter exists
          try {
            if (this.contextTxtEl) {
              const currContextFilter =
                this.contextTxtEl.textContent.toLowerCase();

              if (currContextFilter !== "all") {
                const settingContext = setting
                  .getAttribute("data-global-config-context")
                  .toLowerCase();
                if (settingContext !== currContextFilter) {
                  needToHide = true;
                }
              }
            }
          } catch (e) {}

          if (needToHide) {
            setting.classList.add("hidden");
            settingHiddenCount++;
          }
        } catch (err) {}
      });

      // check multiple settings
      //get settings of tabs except multiples
      const multSettings = this.getMultSettingsFromTab(tab);
      const multSettingCount = multSettings.length;
      let multSettingHiddenCount = 0;
      multSettings.forEach((multSetting) => {
        try {
          let needToHideMult = false;
          const title = multSetting
            .querySelector("h5")
            .textContent.trim()
            .toLowerCase();
          if (!title.includes(inpValue) && inpValue !== "") {
            needToHideMult = true;
          }

          // check context if filter exists
          try {
            if (this.contextTxtEl) {
              const currContextFilter =
                this.contextTxtEl.textContent.toLowerCase();

              if (currContextFilter !== "all") {
                const settingContext = multSetting
                  .getAttribute("data-global-config-context")
                  .toLowerCase();
                if (settingContext !== currContextFilter) {
                  needToHideMult = true;
                }
              }
            }
          } catch (e) {}

          if (needToHideMult) {
            multSetting.classList.add("hidden");
            multSettingHiddenCount++;
          }
        } catch (err) {}
      });

      // check for each multiple groups if all are hidden
      // if so, hide the multiple handler
      const multSettingsHandler = this.contentContainer
        .querySelector(`[data-plugin-item=${tabName}]`)
        .querySelectorAll(`[data-multiple-handler]`);

      for (let i = 0; i < multSettingsHandler.length; i++) {
        // loop en each multiple groups
        const handlerEl = multSettingsHandler[i];
        const multHandlerName = handlerEl.getAttribute("data-multiple-handler");
        const multGroups = this.contentContainer
          .querySelector(`[data-plugin-item=${tabName}]`)
          .querySelectorAll(
            `[data-${this.prefix}-settings-multiple^="${multHandlerName}"]`,
          );
        // check for each if all settings are hidden

        for (let j = 0; j < multGroups.length; j++) {
          const multGroup = multGroups[j];
          let isAllMultSettingHidden = true;
          const settings = multGroup.querySelectorAll(
            `[data-setting-container]`,
          );
          for (let k = 0; k < settings.length; k++) {
            if (!settings[k].classList.contains("hidden")) {
              isAllMultSettingHidden = false;
              break;
            }
          }

          if (isAllMultSettingHidden) {
            handlerEl.classList.add("hidden");
            multGroup.classList.add("hidden");
          }
        }
      }

      // Hide title if multSettingsHandler are hidden
      let isAllGroupsHidden = true;
      for (let i = 0; i < multSettingsHandler.length; i++) {
        const handlerEl = multSettingsHandler[i];
        if (!handlerEl.classList.contains("hidden")) {
          isAllGroupsHidden = false;
          break;
        }
      }

      if (multSettingsHandler.length > 0 && isAllGroupsHidden) {
        const multTitle = this.contentContainer
          .querySelector(`[data-plugin-item=${tabName}]`)
          .querySelector("[data-multiple-title]");
        multTitle.classList.add("hidden");
      }

      //case no setting or no multiple match, check if match at least tab name
      // if no context, else we don't care about name
      if (
        settingCount === settingHiddenCount &&
        multSettingCount === multSettingHiddenCount
      ) {
        const tabName = tab.getAttribute(`data-tab-select-handler`);
        const tabTxt = tab.textContent.trim().toLowerCase();
        let needHideTab = false;
        try {
          if (this.contextTxtEl.textContent.toLowerCase() !== "all")
            needHideTab = true;
        } catch (e) {}

        if (!tabTxt.includes(inpValue)) needHideTab = true;

        if (needHideTab) {
          tab.classList.add("!hidden");

          this.contentContainer
            .querySelector(`[data-plugin-item=${tabName}]`)
            .classList.add("hidden");
        }
      }
    });

    // check current tabs states
    let isAllHidden = true;
    let firstNotHiddenEl = null;
    for (let i = 0; i < this.tabsEls.length; i++) {
      const tab = this.tabsEls[i];
      if (!tab.classList.contains("!hidden")) {
        isAllHidden = false;
        firstNotHiddenEl = tab;
        break;
      }
    }

    // case no tab match
    if (isAllHidden) {
      this.tabContainer
        .querySelector("[data-tab-select-dropdown-btn]")
        .setAttribute("data-tab-id", "no-match");
      return (this.tabContainer.querySelector(
        "[data-tab-select-dropdown-btn] span",
      ).textContent = "No match");
    }

    // click first not hidden tab
    const currTabEl = this.tabContainer.querySelector(
      "[data-tab-select-dropdown-btn]",
    );

    const currTabName = currTabEl.getAttribute("data-tab-id");

    // case previously no match
    if (currTabName === "no-match" && !isAllHidden) {
      return firstNotHiddenEl.click();
    }

    const currTabBtn = this.tabContainer.querySelector(
      `[data-tab-select-handler='${currTabName}']`,
    );

    if (!currTabBtn.classList.contains("!hidden")) {
      return currTabBtn.click();
    }

    if (currTabBtn.classList.contains("!hidden")) {
      return firstNotHiddenEl.click();
    }
  }

  resetFilter() {
    this.tabsEls.forEach((tab) => {
      const tabName = tab.getAttribute(`data-tab-select-handler`);
      //show tab
      tab.classList.remove("!hidden");
      this.contentContainer
        .querySelector(`[data-plugin-item=${tabName}]`)
        .classList.remove("hidden");
      // show no multiple setting
      const settings = this.getSettingsFromTab(tab);
      settings.forEach((setting) => {
        setting.classList.remove("hidden");
      });
      // show multiple setting
      const multSettings = this.getMultSettingsFromTab(tab);
      multSettings.forEach((setting) => {
        setting.classList.remove("hidden");
      });
      // show multiple handler
      const multSettingsHandler = this.contentContainer
        .querySelector(`[data-plugin-item=${tabName}]`)
        .querySelectorAll(`[data-multiple-handler]`);

      const multTitle = this.contentContainer
        .querySelector(`[data-plugin-item=${tabName}]`)
        .querySelector("[data-multiple-title]");

      if (multTitle) {
        multTitle.classList.remove("hidden");
      }

      for (let i = 0; i < multSettingsHandler.length; i++) {
        // loop en each multiple groups
        const handlerEl = multSettingsHandler[i];
        handlerEl.classList.remove("hidden");
        const multHandlerName = handlerEl.getAttribute("data-multiple-handler");
        const multGroups = this.contentContainer
          .querySelector(`[data-plugin-item=${tabName}]`)
          .querySelectorAll(
            `[data-${this.prefix}-settings-multiple^="${multHandlerName}"]`,
          );
        // check for each if all settings are hidden
        for (let j = 0; j < multGroups.length; j++) {
          const multGroup = multGroups[j];
          // avoid if _SCHEMA
          if (
            multGroup
              .getAttribute(`data-${this.prefix}-settings-multiple`)
              .includes("_SCHEMA")
          )
            continue;
          multGroup.classList.remove("hidden");

          const settings = multGroup.querySelectorAll(
            `[data-setting-container]`,
          );
          for (let k = 0; k < settings.length; k++) {
            settings[k].classList.remove("hidden");
          }
        }
      }
    });
  }

  getSettingsFromTab(tabEl) {
    const tabName = tabEl.getAttribute(`data-tab-select-handler`);
    // no multiple settings
    const settingContainer = this.contentContainer
      .querySelector(`[data-plugin-item="${tabName}"]`)
      .querySelector(`[data-plugin-settings]`);
    const settings = settingContainer.querySelectorAll(
      "[data-setting-container]",
    );
    return settings;
  }

  getMultSettingsFromTab(tabEl) {
    const tabName = tabEl.getAttribute(`data-tab-select-handler`);
    const settings = [];
    // get multiple settings
    const settingMultipleGroups = this.contentContainer
      .querySelector(`[data-plugin-item="${tabName}"]`)
      .querySelectorAll(`[data-${this.prefix}-settings-multiple]`);
    for (let i = 0; i < settingMultipleGroups.length; i++) {
      const settingMultipleGroup = settingMultipleGroups[i];
      // case attribute ends with _SCHEMA, continue
      if (
        settingMultipleGroup
          .getAttribute(`data-${this.prefix}-settings-multiple`)
          .includes("_SCHEMA")
      )
        continue;
      const settingsContainer = settingMultipleGroup.querySelectorAll(
        `[data-setting-container]`,
      );

      settingsContainer.forEach((setting) => {
        settings.push(setting);
      });
    }
    return settings;
  }
}

class Tabs {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("click", (e) => {
      try {
        if (e.target.closest("button").hasAttribute("data-tab-handler")) {
          //get needed data
          const tab = e.target.closest("button");
          const tabAtt = tab.getAttribute("data-tab-handler");
          const container = tab.closest("div[data-service-content]");
          // change style
          this.resetTabsStyle(container);
          this.highlightClicked(container, tabAtt);
          this.hideAllSettings(container);
          this.showSettingClicked(container, tabAtt);
        }
      } catch (err) {}
    });
  }

  resetTabsStyle(container) {
    //reset desktop style
    const tabsEk = container.querySelectorAll("button[data-tab-handler]");
    tabsEk.forEach((tab) => {
      tab.classList.remove("active");
    });
  }

  highlightClicked(container, tabAtt) {
    //desktop case
    const tab = container.querySelector(`button[data-tab-handler='${tabAtt}']`);
    tab.classList.add("active");
  }

  hideAllSettings(container) {
    const tabsContent = container.querySelectorAll("[data-tab-item]");

    tabsContent.forEach((tabContent) => {
      tabContent.classList.add("hidden");
    });
  }

  showSettingClicked(container, tabAtt) {
    const tabContent = container.querySelector(`[data-tab-item='${tabAtt}']`);
    tabContent.classList.remove("hidden");
  }
}

class CheckNoMatchFilter {
  constructor(
    input,
    type,
    elsToCheck,
    elContainer,
    noMatchEl,
    classToCheck = "hidden",
  ) {
    this.input = input;
    this.type = type;
    this.elsToCheck = elsToCheck;
    this.elContainer = elContainer;
    this.noMatchEl = noMatchEl;
    this.classToCheck = classToCheck;
    this.init();
  }

  init() {
    if (!this.input || !this.elsToCheck || !this.noMatchEl) return;

    const event = this.type === "input" ? "input" : "click";

    if (!this.input.length) {
      this.input.addEventListener(event, () => {
        this.check();
      });
    }

    if (this.input.length) {
      this.input.forEach((inp) => {
        inp.addEventListener(event, () => {
          this.check();
        });
      });
    }
  }

  check() {
    setTimeout(() => {
      let isAllHidden = true;
      for (let i = 0; i < this.elsToCheck.length; i++) {
        const el = this.elsToCheck[i];
        if (!el.classList.contains(this.classToCheck)) {
          isAllHidden = false;
          break;
        }
      }

      if (isAllHidden) {
        this.noMatchEl.classList.remove(this.classToCheck);
        this.elContainer
          ? this.elContainer.classList.add(this.classToCheck)
          : false;
      }

      if (!isAllHidden) {
        this.elContainer
          ? this.elContainer.classList.remove(this.classToCheck)
          : false;
        this.noMatchEl.classList.add(this.classToCheck);
      }
    }, 20);
  }
}

class showInvalid {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("change", (e) => {
      this.setInvalidState(e);
    });

    window.addEventListener("input", (e) => {
      this.setInvalidState(e);
    });

    window.addEventListener("click", (e) => {
      this.setInvalidState(e);
    });
  }

  setInvalidState(e) {
    try {
      if (e.target.hasAttribute("data-setting-input")) {
        const settingName = e.target.getAttribute("id");
        const invalidEl = document.querySelector(
          `[data-invalid=${settingName}]`,
        );
        const isValid = e.target.validity.valid;

        if (isValid) {
          e.target.classList.remove("invalid");
          invalidEl.classList.add("hidden", "md:hidden");
          return;
        }
        if (!isValid) {
          e.target.classList.add("invalid");
          invalidEl.classList.remove("hidden", "md:hidden");
          return;
        }
      }
    } catch (e) {}
  }
}

export {
  Popover,
  Tabs,
  TabsSelect,
  FormatValue,
  FilterSettings,
  CheckNoMatchFilter,
  showInvalid,
};
