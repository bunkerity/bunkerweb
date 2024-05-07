class Popover {
  constructor() {
    this.init();
    this.visiblePopover = null;
    this.relateBtn = null;
  }

  init() {
    window.addEventListener(
      "scroll",
      (e) => {
        try {
          this.hidePopover(this.relateBtn);
        } catch (e) {}
      },
      true,
    );

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

    this.visiblePopover = popover;
    this.relateBtn = btn;
    this.updatePos();

    setTimeout(() => {
      popover.classList.remove("opacity-0");
    }, 150);
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

  updatePos() {
    const btn = this.relateBtn;
    const popover = this.visiblePopover;

    const btnRect = btn.getBoundingClientRect();
    const btnTop = btnRect.y;
    const btnLeft = btnRect.x;

    popover.style.top = `${
      btnTop - popover.getBoundingClientRect().height + 20
    }px`;
    popover.style.left = `${
      btnLeft - popover.getBoundingClientRect().width / 3
    }px`;
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
    try {
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
    } catch (e) {}
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
    const combobox = dropdown.querySelector("[data-combobox]");
    if (combobox) {
      // simulate clear combobox with keyboard
      combobox.value = "";
    }
    dropdown.classList.toggle("hidden");
    dropdown.classList.toggle("flex");

    // Case open, try to focus on combobox input
    // Unless already input focused (avoid conflict with search)
    if (
      !dropdown.classList.contains("hidden") &&
      combobox &&
      combobox.getAttribute("data-focus") !== "false"
    ) {
      combobox.focus();
    }

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
    this.typeTxtEl = document.querySelector(
      `span[data-${this.prefix}-setting-select-text="type"]`,
    );
    this.comboboxEl = document.querySelector(
      `[data-${this.prefix}-tabs-select] [data-combobox]`,
    );
    this.isComboCheck = false;
    this.tabContainer = tabContainer;
    this.contentContainer = contentContainer;
    this.tabsEls = this.tabContainer.querySelectorAll(
      `[data-tab-select-handler]`,
    );
    this.comboboxEl = this.tabContainer
      .querySelector("[data-tab-select-dropdown]")
      .querySelector("[data-combobox]");

    this.init();
  }

  init() {
    window.addEventListener("DOMContentLoaded", () => {
      if (this.input) {
        this.input.addEventListener("input", () => {
          this.runFilter();
        });
      }

      // Update plugin items based on current input
      if (this.comboboxEl) {
        this.comboboxEl.addEventListener("input", () => {
          this.runComboFilter();
        });

        // Allow to run combobox filter when opening dropdown (because reset and focus on open)
        this.comboboxEl.addEventListener("focusin", () => {
          this.runComboFilter();
        });
      }

      window.addEventListener("click", (e) => {
        try {
          if (
            (e.target.hasAttribute(
              `data-${this.prefix}-setting-select-dropdown-btn`,
            ) &&
              e.target.getAttribute(
                `data-${this.prefix}-setting-select-dropdown-btn`,
              ) === `context`) ||
            (e.target.hasAttribute(
              `data-${this.prefix}-setting-select-dropdown-btn`,
            ) &&
              e.target.getAttribute(
                `data-${this.prefix}-setting-select-dropdown-btn`,
              ) === `type`)
          ) {
            return this.runFilter();
          }
        } catch (e) {}
      });
    });
  }

  runComboFilter() {
    // Case combobox, we want to filter tabs only and not settings
    this.tabsEls.forEach((tab) => {
      tab.classList.remove("hidden");

      const tabName = tab.getAttribute(`data-tab-select-handler`);
      // check tab name matching combobox value
      if (this.comboboxEl) {
        const comboboxValue = this.comboboxEl.value;
        if (!tabName.toLowerCase().includes(comboboxValue.toLowerCase())) {
          tab.classList.add("hidden");
          return;
        }
      }
    });
    return;
  }

  runFilter() {
    // Reset previous state to start fresh
    this.resetFilter();
    // get current tab, this will be used to show other plugin tab if current is hidden after filter
    const tabNameBeforeFilter =
      this.tabContainer
        ?.querySelector("[data-tab-select-dropdown-btn]")
        ?.getAttribute("data-tab-id") || "";
    //get inp format
    const inpValue = this.input.value.trim().toLowerCase().replaceAll("_", " ");

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
          // Try to get
          const settingEl =
            setting.querySelector("input")?.getAttribute("id") ||
            setting.querySelector("select")?.getAttribute("id") ||
            "";
          const settingId = settingEl.trim().toLowerCase().replaceAll("_", " ");

          if (
            !title
              .trim()
              .toLowerCase()
              .replaceAll("_", " ")
              .includes(inpValue) &&
            inpValue !== "" &&
            !settingId.includes(inpValue)
          ) {
            needToHide = true;
          }

          // check context if filter exists
          try {
            if (this.contextTxtEl) {
              const currContextFilter =
                this.contextTxtEl.textContent.toLowerCase();

              if (currContextFilter !== "all") {
                const settingContext = setting
                  .getAttribute(`data-${this.prefix}-context`)
                  .toLowerCase();
                if (settingContext !== currContextFilter) {
                  needToHide = true;
                }
              }
            }
          } catch (e) {}

          // check type if filter exists
          try {
            if (this.typeTxtEl) {
              const currTypeFilter = this.typeTxtEl.textContent.toLowerCase();

              if (currTypeFilter !== "all") {
                const settingContext = setting
                  .getAttribute(`data-${this.prefix}-type`)
                  .toLowerCase();
                if (settingContext !== currTypeFilter) {
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
          const settingEl =
            multSetting.querySelector("input")?.getAttribute("id") ||
            setting.querySelector("select")?.getAttribute("id") ||
            "";
          const settingId = settingEl.trim().toLowerCase().replaceAll("_", " ");
          if (
            !title
              .trim()
              .toLowerCase()
              .replaceAll("_", " ")
              .includes(inpValue) &&
            inpValue !== "" &&
            !settingId.includes(inpValue)
          ) {
            needToHideMult = true;
          }

          // check context if filter exists
          try {
            if (this.contextTxtEl) {
              const currContextFilter =
                this.contextTxtEl.textContent.toLowerCase();

              if (currContextFilter !== "all") {
                const settingContext = multSetting
                  .getAttribute(`data-${this.prefix}-context`)
                  .toLowerCase();
                if (settingContext !== currContextFilter) {
                  needToHideMult = true;
                }
              }
            }
          } catch (e) {}

          try {
            if (this.typeTxtEl) {
              const currtypeFilter = this.typeTxtEl.textContent.toLowerCase();

              if (currtypeFilter !== "all") {
                const settingtype = multSetting
                  .getAttribute(`data-${this.prefix}-type`)
                  .toLowerCase();
                if (settingtype !== currtypeFilter) {
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

      // case no setting or no multiple match, check if match at least tab name
      // if no context, else we don't care about name
      if (
        settingCount === settingHiddenCount &&
        multSettingCount === multSettingHiddenCount
      ) {
        const tabName = tab.getAttribute(`data-tab-select-handler`);
        const tabTxt = tab.textContent.trim().toLowerCase();
        const tabType = tab.getAttribute(`data-tab-plugin-type`);
        let needHideTab = false;
        try {
          if (
            this.contextTxtEl &&
            this.contextTxtEl.textContent.toLowerCase() !== "all"
          )
            needHideTab = true;
        } catch (e) {}

        try {
          if (
            this.typeTxtEl &&
            this.typeTxtEl.textContent.toLowerCase() !== tabType
          )
            needHideTab = true;
        } catch (e) {}

        if (
          !tabTxt.trim().toLowerCase().replaceAll("_", " ").includes(inpValue)
        )
          needHideTab = true;

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
      // we want to show message "No match"
      this.tabContainer
        .querySelector("[data-tab-select-dropdown-btn]")
        .setAttribute("data-tab-id", "no-match");
      this.tabContainer.querySelector(
        "[data-tab-select-dropdown-btn] span",
      ).textContent = "No match";
      // we want to close dropdown in case open previously
      this.toggleDropdown(true, true, false);
      return;
    }

    // case at least one match
    const currTabBtn = this.tabContainer.querySelector(
      `[data-tab-select-handler='${tabNameBeforeFilter}']`,
    );

    // case the previous plugin is still visible, set is as active by clicking it again
    if (currTabBtn && !currTabBtn.classList.contains("!hidden")) {
      currTabBtn.click();
    }

    // case the previous plugin is hidden, click on the first not hidden tab
    if (currTabBtn?.classList?.contains("!hidden") || !currTabBtn) {
      firstNotHiddenEl.click();
    }

    // furthermore, open dropdown so user can see remain plugins in case the first one is not the one he is looking for
    // and if more than one plugin available
    // but we want to avoid dropdown open if  active element is input keyword and value is empty
    if (document.activeElement === this.input && this.input.value === "")
      return;

    const hiddenTabsEl = this.tabContainer.querySelectorAll(
      `[data-tab-select-handler][class*="!hidden"]`,
    );

    if (hiddenTabsEl.length < this.tabsEls.length - 1)
      this.toggleDropdown(true, false, true);
    return;
  }

  toggleDropdown(
    avoidComboFocus = false,
    disableOpen = false,
    disableClose = false,
  ) {
    // avoid this on mobile
    if (window.innerWidth < 768) return;
    const dropdownEl = this.tabContainer.querySelector(
      "[data-tab-select-dropdown]",
    );
    const dropdownBtn = this.tabContainer.querySelector(
      "[data-tab-select-dropdown-btn]",
    );
    if (this.comboboxEl && avoidComboFocus)
      this.comboboxEl.setAttribute("data-focus", "false");
    let canClick = true;
    // check if can click based on next dropdown state
    if (disableClose && !dropdownEl.classList.contains("hidden"))
      canClick = false;
    if (disableOpen && dropdownEl.classList.contains("hidden"))
      canClick = false;
    if (canClick) dropdownBtn.click();
    // Case avoid focus on combobox, we need to reset here because the focusin event is not triggered
    if (this.comboboxEl && avoidComboFocus) this.runComboFilter();
    // Reset to default state
    if (this.comboboxEl) this.comboboxEl.setAttribute("data-focus", "true");
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
    this.isChecking = false;
  }

  init() {
    window.addEventListener("change", (e) => {
      if (this.isChecking) return;
      this.setInvalidState(e);
    });

    window.addEventListener("input", (e) => {
      if (this.isChecking) return;
      this.setInvalidState(e);
    });

    window.addEventListener("click", (e) => {
      if (this.isChecking) return;
      this.setInvalidState(e);
    });

    window.addEventListener("focusin", (e) => {
      if (this.isChecking) return;
      this.setInvalidState(e);
    });
  }

  setInvalidState(e) {
    this.isChecking = true;
    try {
      setTimeout(() => {
        const elsToCheck = [
          e.target,
          ...document.querySelectorAll("input.invalid"),
        ];
        elsToCheck.forEach((el) => {
          if (el.hasAttribute("data-setting-input")) {
            const settingName = el.getAttribute("id");
            const invalidEl = el
              .closest("form")
              .querySelector(`[data-invalid=${settingName}]`);
            const isValid = el.validity.valid;

            if (isValid) {
              el.classList.remove("invalid");
              invalidEl.classList.add("hidden", "md:hidden");
              return;
            }
            if (!isValid) {
              el.classList.add("invalid");
              invalidEl.classList.remove("hidden", "md:hidden");
              return;
            }
          }
        });
        this.isChecking = false;
      }, 20);
    } catch (e) {
      this.isChecking = false;
    }
  }
}

class Settings {
  constructor(mode, formEl, prefix = "services") {
    this.prefix = prefix;
    this.container = formEl;
    this.mode = mode;

    this.serverNameInps = this.container.querySelectorAll(
      'input[name="SERVER_NAME"][data-setting-input]',
    );

    this.submitBtn = this.container.querySelector(
      `button[data-${this.prefix}-modal-submit]`,
    );
    this.currAction = "";
    this.currMethod = "";
    this.oldServName = "";
    this.setMethodUI = false;
    this.forceEnabled = false;
    this.emptyServerName = false;
    this.currSettings = {};
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
    if (!this.emptyServerName) return;
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
        inpName === "CONFIG_NAME" ||
        inp.hasAttribute("data-combobox")
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
    // Check if pro
    const proDisabled = inp
      .closest("[data-plugin-item]")
      .hasAttribute("data-pro-disabled")
      ? true
      : false;
    if (proDisabled) return inp.setAttribute("disabled", "");
    if (method === "ui" || method === "default") {
      inp.removeAttribute("disabled");
    } else {
      inp.setAttribute("disabled", "");
    }
  }

  updateData(
    action,
    oldServName,
    operation,
    settings,
    setMethodUI,
    forceEnabled,
    emptyServerName,
  ) {
    // Get global needed data
    this.currAction = action;
    this.oldServName = oldServName;
    this.operation = operation;
    this.currSettings = settings;
    this.setMethodUI = setMethodUI;
    this.forceEnabled = forceEnabled;
    this.emptyServerName = emptyServerName;

    this.updateOperation();
    this.updateOldNameValue();
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

  // Avoid multiple settings because it is handle by Multiple class
  getRegularInps() {
    const settings = JSON.parse(JSON.stringify(this.currSettings));
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

  setRegularInps() {
    const settings = this.getRegularInps();
    this.setSettingsByData(settings);
  }

  setSettingsByData(settings) {
    // Case we have settings, like when we edit a service
    // We need to update the settings with the right values
    if (Object.keys(settings).length > 0) {
      // Delete settings that doesn't match DOM elements
      const namesToDelete = [];
      for (const [key, data] of Object.entries(settings)) {
        try {
          const inps = this.container.querySelectorAll(`[name='${key}']`);
        } catch (err) {
          namesToDelete.push(key);
        }
      }

      namesToDelete.forEach((name) => {
        delete settings[name];
      });

      // update DOM value
      for (const [key, data] of Object.entries(settings)) {
        //change format to match id
        const value = data["value"];
        const method = this.setMethodUI ? "ui" : data["method"];
        const global = data["global"];
        try {
          // get only inputs without attribute data-is-multiple
          const inps = this.container.querySelectorAll(`[name='${key}']`);

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

            const proDisabled = inp
              .closest("[data-plugin-item]")
              .hasAttribute("data-pro-disabled")
              ? true
              : false;

            if (proDisabled) return inp.setAttribute("disabled", "");

            if (this.forceEnabled) return inp.removeAttribute("disabled");

            if (method === "ui" || method === "default") {
              inp.removeAttribute("disabled");
            } else {
              inp.setAttribute("disabled", "");
            }

            if (global) inp.removeAttribute("disabled");
          });
        } catch (err) {}
      }
    }
  }

  getSuffixData(name) {
    // check if last part after _ is a number
    const suffix = name.substring(name.lastIndexOf("_") + 1);
    const isNum = !isNaN(suffix);
    const suffixLessIfNum = isNum
      ? name.substring(0, name.lastIndexOf("_"))
      : name;
    return [suffix, isNum, suffixLessIfNum];
  }
}

class SettingsMultiple extends Settings {
  constructor(mode, formEl, multSettingsName, prefix = "services") {
    super(mode, formEl, prefix);
    this.multSettingsName = multSettingsName;

    this.initMultiple();
  }

  initMultiple() {
    this.container.addEventListener("load", () => {
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
          if (this.isAvoidAction(e.target)) return;
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
            const [containerSuffix, containerIsNum, containerName] =
              this.getSuffixData(ctnrName);
            if (containerIsNum && containerSuffix > topNum)
              topNum = containerIsNum;
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

  isAvoidAction(target) {
    // check that not disabled pro plugin
    const proDisabled = target
      .closest("[data-plugin-item]")
      .hasAttribute("data-pro-disabled")
      ? true
      : false;
      
    return proDisabled;
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

  setMultipleInps() {
    //remove all multiples
    this.removePrevMultiples();
    //keep only multiple settings value
    const multipleSettings = this.getMultiplesOnly();

    const sortMultiples =
      this.sortMultipleByContainerAndSuffixe(multipleSettings);
    // Need to set method as ui if clone
    this.setMultipleToDOM(sortMultiples);
    this.setSettingsByData(multipleSettings);
    // Show at least one mult group
    this.addOneMultGroup();
  }

  //put multiple on the right plugin, on schema container
  setMultipleToDOM(sortMultObj) {
    // We want to loop on each schema container
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

        for (const [name, data] of Object.entries(settings)) {
          //get setting container of clone container
          const settingContainer = schemaCtnrClone.querySelector(
            `[data-setting-container="${name}"]`,
          );
        }
        //send schema clone to DOM and show it
        this.showClone(schemaCtnr, schemaCtnrClone);
      }
    }
  }

  getMultiplesOnly() {
    const settings = JSON.parse(JSON.stringify(this.currSettings));
    // Keep only multiples
    for (const [key, data] of Object.entries(settings)) {
      // remove suffixe if exists
      //suffixe start with number 1, if none give arbitrary 0 value to store on same group
      const [suffixe, isSuffixe, name] = this.getSuffixData(key);
      if (!this.multSettingsName.includes(name)) delete settings[key];
    }

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

  changeCloneSuffix(schemaCtnrClone, suffix) {
    //rename multiple container
    schemaCtnrClone.setAttribute(
      `data-${this.prefix}-settings-multiple`,
      schemaCtnrClone
        .getAttribute(`data-${this.prefix}-settings-multiple`)
        .replace("_SCHEMA", suffix),
    );

    // Get all elemennts by attribute to update _SCHEMA by suffix
    const attributes = [
      "data-setting-container",
      "id",
      "data-invalid",
      "for",
      "data-popover-btn",
      "data-popover-content",
      "name",
    ];

    attributes.forEach((att) => {
      const attEls = schemaCtnrClone.querySelectorAll(`[${att}]`);
      attEls.forEach((attEl) => {
        attEl.setAttribute(
          att,
          attEl.getAttribute(att).replace("_SCHEMA", suffix),
        );
      });
    });

    //rename title
    const titles = schemaCtnrClone.querySelectorAll("h5");
    titles.forEach((title) => {
      const text = title.textContent;
      title.textContent = `${text} ${
        suffix ? `#${suffix.replace("_", "")}` : ``
      }`;
    });
  }
}

class SettingsEditor extends SettingsMultiple {
  constructor(mode, formEl, multSettingsName, prefix = "services") {
    super(mode, formEl, multSettingsName, prefix);
    this.darkMode = document.querySelector("[data-dark-toggle]");
    this.isDarkMode = this.darkMode.checked;
    // add editor for configs in simple mode
    this.editorEls = [];
    this.initEditors();
  }

  initEditors() {
    this.darkMode.addEventListener("click", (e) => {
      this.isDarkMode = e.target.checked;
      this.updateEditorMode();
    });
  }

  setupEditorsInstance() {
    this.editorEls.forEach((editor) => {
      const editorEl = editor.container;
      // we want to link editor to inp when sending form
      const linkInp = editorEl
        .closest("[data-editor-container]")
        .querySelector(`textarea[data-editor-input]`);
      // format name to get format TYPE_CONFIG_NAME
      linkInp.addEventListener("change", () => {
        const filename = linkInp?.getAttribute("data-filename")
          ? linkInp?.getAttribute("data-filename").replaceAll("_", "-")
          : linkInp?.getAttribute("data-default-filename").replaceAll("_", "-");
        const type = linkInp
          ?.getAttribute("data-config-type")
          .replaceAll("_", "-");
        linkInp.setAttribute("name", `custom_config_${type}_${filename}`);
      });

      editor.on("change", () => {
        linkInp.value = editor.getValue();
      });

      // we can link inp to input file name to update it if exists
      const inpFileName = editorEl
        .closest("[data-editor-container]")
        .querySelector(`input[data-editor-filename]`);

      if (inpFileName) {
        inpFileName.addEventListener("input", () => {
          linkInp.setAttribute("data-filename", inpFileName.value);
          // dispatch event to inp to ensure it is updated
          const event = new Event("change");
          linkInp.dispatchEvent(event);
        });
        inpFileName.addEventListener("change", () => {
          linkInp.setAttribute("data-filename", inpFileName.value);
          // dispatch event to inp to ensure it is updated
          const event = new Event("change");
          linkInp.dispatchEvent(event);
        });
      }
    });
  }

  setEditorSettings() {
    this.resetEditorsInstAndDOM();
    this.addDefaultEditorIfNone();
    this.setupEditorsInstance();
    this.updateEditorMode();
  }

  addDefaultEditorIfNone() {
    // get containers with _SCHEMA
    const editorContainers = this.container.querySelectorAll(
      "[data-editor-container$='_SCHEMA']",
    );
    editorContainers.forEach((editorContainer) => {
      // Check if others editor exists with same base name
      const editorName = editorContainer
        .getAttribute("data-editor-container")
        .replace("_SCHEMA", "");
      const otherEditors = this.container.querySelectorAll(
        `[data-editor-container*='${editorName}']`,
      );
      if (otherEditors.length > 1) return;
      // Add default editor
      const defaultType = editorContainer
        .getAttribute("data-default-type")
        .replaceAll("_", "-");
      const defaultName = editorContainer
        .getAttribute("data-default-name")
        .replaceAll("_", "-");
      this.addOneEditor(editorContainer, defaultType, defaultName, 1, "");
    });
  }

  resetEditorsInstAndDOM() {
    // reset previous editors
    this.editorEls.forEach((editor) => {
      const editorContainer = editor.container.closest(
        "[data-editor-container]",
      );
      editorContainer.remove();
      editor.destroy();
    });

    this.editorEls = [];
    // get only container ending with _SCHEMA
    const editorContainers = this.container.querySelectorAll(
      "[data-editor-container$='_SCHEMA']",
    );
    const configsSettings = this.getEditorSettings();
    // Create instances on the right containers
    editorContainers.forEach((editorContainer) => {
      const contName = editorContainer
        .getAttribute("data-editor-container")
        .replace("_SCHEMA", "");
      // Loop on each custom config settings that match same prefix as key
      // And create instance
      for (const [key, data] of Object.entries(configsSettings)) {
        if (!key.startsWith(contName)) continue;
        const editorName = data["name"].replaceAll("_", "-");
        const editorType = data["type"].replaceAll("_", "-");
        const editorValue = data["value"];
        const [num, isNum, name] = this.getSuffixData(key);
        this.addOneEditor(
          editorContainer,
          editorType,
          editorName,
          num,
          editorValue,
        );
      }
    });
  }

  addOneEditor(container, type, name, num, value) {
    const contName = container
      .getAttribute("data-editor-container")
      .replace("_SCHEMA", "");
    const containerClone = container.cloneNode(true);
    // update attributes
    containerClone.setAttribute("data-editor-container", `${contName}_${num}`);
    const editor = containerClone.querySelector(`[data-editor]`);
    if (editor) {
      editor.setAttribute("id", `${contName}_${num}`);
      editor.setAttribute("name", `${contName}_${num}`);
    }
    const filenameInp = containerClone.querySelector(
      `input[data-editor-filename]`,
    );
    if (filenameInp) filenameInp.value = name;
    const hiddenInp = containerClone.querySelector(
      `textarea[data-editor-input]`,
    );
    if (hiddenInp) {
      hiddenInp.setAttribute("data-config-type", type);
      hiddenInp.setAttribute("data-filename", name);
      hiddenInp.setAttribute("name", `custom_config_${type}_${name}`);
    }
    // append to DOM and show as sibling of the original container
    container.insertAdjacentElement("afterend", containerClone);
    containerClone.classList.remove("hidden");
    // instantiate editor
    const editorInst = ace.edit(editor);
    editorInst.setValue(value);
    this.editorEls.push(editorInst);
  }

  getEditorSettings() {
    const settings = JSON.parse(JSON.stringify(this.currSettings));
    const configsSettings = {};
    for (const [key, data] of Object.entries(settings)) {
      if (key.startsWith("CUSTOM_CONFIG")) {
        configsSettings[key] = data;
      }
    }
    return configsSettings;
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
}

class SettingsAdvanced extends SettingsEditor {
  constructor(formEl, multSettingsName, prefix = "services") {
    super("advanced", formEl, multSettingsName, prefix);
    this.initAdvanced();
  }

  initAdvanced() {
    window.addEventListener("DOMContentLoaded", () => {
      this.container.addEventListener("input", (e) => {
        this.checkVisibleInpsValidity();
      });
    });
  }

  setAdvanced(
    action,
    oldServName,
    operation,
    settings,
    setMethodUI = false,
    forceEnabled = false,
    emptyServerName = false,
  ) {
    this.updateData(
      action,
      oldServName,
      operation,
      settings,
      setMethodUI,
      forceEnabled,
      emptyServerName,
    );
    this.setSettingsAdvanced();
    this.resetServerName();
    this.checkVisibleInpsValidity();
  }

  setSettingsAdvanced() {
    this.setSettingsByAtt();
    this.setRegularInps();
    this.setMultipleInps();
  }

  checkVisibleInpsValidity() {
    try {
      const inps = this.container.querySelectorAll(
        "[data-plugin-item]:not(.hidden) input[data-setting-input], [data-plugin-item][class*='hidden'] input[data-setting-input]",
      );

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

      const errMsg = this.container.querySelector(
        "[data-services-modal-error-msg]",
      );
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
        this.container
          .querySelector("button[data-services-modal-submit]")
          .setAttribute("disabled", "");
      }

      if (isAllValid) {
        errMsg.classList.add("hidden");
        this.container
          .querySelector("button[data-services-modal-submit]")
          .removeAttribute("disabled");
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
  Settings,
  SettingsMultiple,
  SettingsAdvanced,
};
