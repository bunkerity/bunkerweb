class Popover {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("pointerover", (e) => {
      //POPOVER LOGIC
      try {
        if (e.target.closest("svg").hasAttribute(`popover-btn`)) {
          this.showPopover(e.target);
        }
      } catch (err) {}
    });

    window.addEventListener("pointerout", (e) => {
      //POPOVER LOGIC
      try {
        if (e.target.closest("svg").hasAttribute(`popover-btn`)) {
          this.hidePopover(e.target);
        }
      } catch (err) {}
    });
  }

  showPopover(el) {
    const btn = el.closest("svg");
    //toggle curr popover
    const popover = btn.parentElement.querySelector(`[popover-content]`);
    popover.classList.remove("hidden");
  }

  hidePopover(el) {
    const btn = el.closest("svg");
    //toggle curr popover
    const popover = btn.parentElement.querySelector(`[popover-content]`);
    popover.classList.add("hidden");
  }
}

class Tabs {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("click", (e) => {
      try {
        if (
          e.target.closest("button").hasAttribute("tab-handler") ||
          e.target.closest("button").hasAttribute("tab-handler-mobile")
        ) {
          console.log("tab clicked");
          //get needed data
          const tab = e.target.closest("button");
          const tabAtt =
            tab.getAttribute("tab-handler") ||
            tab.getAttribute("tab-handler-mobile");
          const container = tab.closest("div[service-content]");
          // change style
          this.resetTabsStyle(container);
          this.highlightClicked(container, tabAtt);
          //show content
          this.hideAllSettings(container);
          this.showSettingClicked(container, tabAtt);
          //close dropdown and change btn textcontent on mobile
          this.setDropBtnText(container, tabAtt);
          this.closeDropdown(container);
        }
      } catch (err) {}

      try {
        if (e.target.closest("button").hasAttribute("tab-dropdown-btn")) {
          const dropBtn = e.target.closest("button");
          const container = dropBtn.closest("div[service-content]");
          this.toggleDropdown(container);
        }
      } catch (err) {}
    });
  }

  resetTabsStyle(container) {
    //reset desktop style
    const tabsDesktop = container.querySelectorAll("button[tab-handler]");
    tabsDesktop.forEach((tab) => {
      tab.classList.remove("brightness-90", "z-10");
    });
    //reset mobile style
    const tabsMobile = container.querySelectorAll("button[tab-handler-mobile]");
    tabsMobile.forEach((tab) => {
      tab.classList.add("bg-white", "dark:bg-slate-700", "text-gray-700");
      tab.classList.remove(
        "dark:bg-primary",
        "bg-primary",
        "bg-primary",
        "text-gray-300",
        "text-gray-300"
      );
    });
  }

  highlightClicked(container, tabAtt) {
    //desktop case
    const tabDesktop = container.querySelector(
      `button[tab-handler='${tabAtt}']`
    );
    tabDesktop.classList.add("brightness-90", "z-10");

    //mobile case
    const tabMobile = container.querySelector(
      `button[tab-handler-mobile='${tabAtt}']`
    );
    tabMobile.classList.add("dark:bg-primary", "bg-primary", "text-gray-300");
    tabMobile.classList.remove(
      "bg-white",
      "dark:bg-slate-700",
      "text-gray-700"
    );
  }

  hideAllSettings(container) {
    const plugins = container.querySelectorAll("[plugin-item]");
    plugins.forEach((plugin) => {
      plugin.classList.add("hidden");
    });
  }

  showSettingClicked(container, tabAtt) {
    const plugin = container.querySelector(`[plugin-item='${tabAtt}']`);
    plugin.classList.remove("hidden");
  }

  setDropBtnText(container, tabAtt) {
    const dropBtn = container.querySelector("[tab-dropdown-btn]");
    dropBtn.querySelector("span").textContent = tabAtt;
  }

  closeDropdown(container) {
    const dropdown = container.querySelector("[tab-dropdown]");
    dropdown.classList.add("hidden");
    dropdown.classList.remove("flex");
  }

  toggleDropdown(container) {
    const dropdown = container.querySelector("[tab-dropdown]");
    dropdown.classList.toggle("hidden");
    dropdown.classList.toggle("flex");
  }
}

class FormatValue {
  constructor() {
    this.inputs = document.querySelectorAll("[value]");
    this.init();
  }

  init() {
    this.inputs.forEach((inp) => {
      inp.setAttribute("value", inp.getAttribute("value").trim());
    });
  }
}

class FilterSettings {
  constructor(inputID, container) {
    this.input = document.querySelector(`input#${inputID}`);
    //DESKTOP
    this.container = document.querySelector(container);
    this.deskTabs = this.container.querySelectorAll(`[tab-handler]`);
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
          const tabName = tab.getAttribute(`tab-handler`);
          //hide mobile and desk tabs
          tab.classList.add("hidden");
          this.container
            .querySelector(`[tab-handler-mobile="${tabName}"]`)
            .classList.add("hidden");
          this.container
            .querySelector(`[plugin-item=${tabName}]`)
            .querySelector("[setting-header]")

            .classList.add("hidden");
        }
      });
    });
  }

  resetFilter() {
    this.deskTabs.forEach((tab) => {
      const tabName = tab.getAttribute(`tab-handler`);
      //hide mobile and desk tabs
      tab.classList.remove("hidden");
      this.container
        .querySelector(`[tab-handler-mobile="${tabName}"]`)
        .classList.remove("hidden");
      this.container
        .querySelector(`[plugin-item=${tabName}]`)
        .querySelector("[setting-header]")
        .classList.remove("hidden");
      const settings = this.getSettingsFromTab(tab);
      settings.forEach((setting) => {
        setting.classList.remove("hidden");
      });
    });
  }

  getSettingsFromTab(tabEl) {
    const tabName = tabEl.getAttribute(`tab-handler`);
    const settingContainer = this.container
      .querySelector(`[plugin-item="${tabName}"]`)
      .querySelector(`[plugin-settings]`);
    const settings = settingContainer.querySelectorAll("[setting-container]");
    return settings;
  }
}

export { Popover, Tabs, FormatValue, FilterSettings };
