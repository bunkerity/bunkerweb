class Popover {
  constructor(container, prefix) {
    this.prefix = prefix;
    this.container = container;
    this.popoverContainer = document.querySelector(`${this.container}`);
    this.init();
  }

  init() {
    let popoverCount = 0; //for auto hide
    let btnPopoverAtt = ""; //to manage info btn clicked

    this.popoverContainer.addEventListener("click", (e) => {
      //POPOVER LOGIC
      try {
        if (e.target.closest("svg").hasAttribute(`${this.prefix}-info-btn`)) {
          const btnPop = e.target.closest("svg");
          //toggle curr popover
          const popover = btnPop.parentElement.querySelector(
            `[${this.prefix}-info-popover]`
          );
          popover.classList.toggle("hidden");

          //get a btn att if none
          if (btnPopoverAtt === "")
            btnPopoverAtt = btnPop.getAttribute(`${this.prefix}-info-btn`);

          //compare prev btn and curr
          //hide prev popover if not the same
          if (
            btnPopoverAtt !== "" &&
            btnPopoverAtt !== btnPop.getAttribute(`${this.prefix}-info-btn`)
          ) {
            const prevPopover = document.querySelector(
              `[${this.prefix}-info-popover="${btnPopoverAtt}"]`
            );
            prevPopover.classList.add("hidden");
            btnPopoverAtt = btnPop.getAttribute(`${this.prefix}-info-btn`);
          }

          //hide popover after an amount of time
          popoverCount++;
          const currCount = popoverCount;
          setTimeout(() => {
            //if another click on same infoBtn, restart hidden
            if (currCount === popoverCount) popover.classList.add("hidden");
          }, 3000);
        }
      } catch (err) {}
    });
  }
}

class Tabs {
  constructor(container, prefix) {
    this.prefix = prefix;
    this.container = container;
    this.tabsContainer = document.querySelector(`${this.container}`);
    //DESKTOP
    this.desktopBtns = document.querySelectorAll(
      `[${this.prefix}-tabs-desktop] button`
    );
    //MOBILE
    this.mobileBtn = document.querySelector(`[${this.prefix}-mobile-select]`);
    this.mobileBtnTxt = this.mobileBtn.querySelector(`span`);
    this.mobileBtnSVG = document.querySelector(
      `[${this.prefix}-mobile-chevron]`
    );
    this.mobileDropdown = document.querySelector(
      `[${this.prefix}-mobile-dropdown]`
    );
    this.mobileDropdownEls = this.mobileDropdown.querySelectorAll(`button`);
    this.mobileBtn.addEventListener(`click`, this.toggleDropdown.bind(this));
    //FORM
    this.settingContainers = document.querySelectorAll(`[${this.prefix}-item]`);
    this.generalSettings = document.querySelector(
      `[${this.prefix}-item='general']`
    );
    this.initTabs();
    this.initDisplay();
  }

  initTabs() {
    //show first element
    window.addEventListener("load", () => {
      try {
        document.querySelector("button[services-item-handler]").click();
        document.querySelector("button[services-mobile-item-handler]").click();
      } catch (err) {}
    });

    this.tabsContainer.addEventListener("click", (e) => {
      //MOBILE TABS LOGIC
      try {
        if (
          !e.target.hasAttribute(`${this.prefix}-mobile-info-btn`) &&
          e.target.hasAttribute(`${this.prefix}-mobile-item-handler`)
        ) {
          //change text to select btn
          const tab = e.target.closest("button");
          const tabAtt = tab.getAttribute(`${this.prefix}-mobile-item-handler`);
          this.mobileBtnTxt.textContent = tab.childNodes[0].textContent;
          //reset all tabs style
          this.resetMobTabStyle();
          //highlight chosen one
          this.highlightMobClicked(tab);
          //show settings
          this.showRightSetting(tabAtt);
          //close dropdown
          this.toggleDropdown();
        }
      } catch (err) {}
      //DESKTOP TABS LOGIC
      try {
        if (
          !e.target.hasAttribute(`${this.prefix}-info-btn`) &&
          e.target.closest("button").hasAttribute(`${this.prefix}-item-handler`)
        ) {
          const tab = e.target.closest("button");
          const tabAtt = tab.getAttribute(`${this.prefix}-item-handler`);
          //style
          this.resetDeskStyle();
          tab.classList.add("brightness-95", "z-10");
          //show content
          this.showRightSetting(tabAtt);
        }
      } catch (err) {}
    });
  }

  resetDeskStyle() {
    this.desktopBtns.forEach((tab) => {
      tab.classList.remove("brightness-95", "z-10");
    });
  }

  resetMobTabStyle() {
    this.mobileDropdownEls.forEach((tab) => {
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

  highlightMobClicked(tabEl) {
    tabEl.classList.add("dark:bg-primary", "bg-primary", "text-gray-300");
    tabEl.classList.remove("bg-white", "dark:bg-slate-700", "text-gray-700");
  }

  initDisplay() {
    //show general setting or
    //first setting list if doesn't exist (like in services)
    //on mobile and desktop
    if (this.generalSettings === null) {
      //desktop
      document
        .querySelector(
          `[${this.prefix}-tabs-desktop] [${this.prefix}-item-handler]`
        )
        .click();
      //mobile
      document
        .querySelector(
          `[${this.prefix}-tabs-mobile] [${this.prefix}-mobile-item-handler]`
        )
        .click();
      this.toggleDropdown();
    }
  }

  showRightSetting(tabAtt) {
    this.settingContainers.forEach((container) => {
      if (container.getAttribute(`${this.prefix}-item`) === tabAtt)
        container.classList.remove("hidden");
      if (container.getAttribute(`${this.prefix}-item`) !== tabAtt)
        container.classList.add("hidden");
    });
  }

  toggleDropdown() {
    this.mobileDropdown.classList.toggle("hidden");
    this.mobileDropdown.classList.toggle("flex");
    this.mobileBtnSVG.classList.toggle("rotate-180");
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

export { Popover, Tabs, FormatValue };
