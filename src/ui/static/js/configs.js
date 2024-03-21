import {
  FolderNav,
  FolderEditor,
  FolderModal,
  FolderDropdown,
} from "./utils/file.manager.js";

class Dropdown {
  constructor(prefix = "configs") {
    this.prefix = prefix;
    this.container = document.querySelector("main");
    this.lastDrop = "";
    this.initDropdown();
  }

  initDropdown() {
    this.container.addEventListener("click", (e) => {
      //SELECT BTN LOGIC
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`data-${this.prefix}-setting-select`) &&
          !e.target.closest("button").hasAttribute(`disabled`)
        ) {
          const btnName = e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select`);
          if (this.lastDrop !== btnName) {
            this.lastDrop = btnName;
            this.closeAllDrop();
          }

          this.toggleSelectBtn(e);
        }
      } catch (err) {}
      //SELECT DROPDOWN BTN LOGIC
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`data-${this.prefix}-setting-select-dropdown-btn`)
        ) {
          const btn = e.target.closest("button");
          const btnValue = btn.getAttribute("value");
          const btnSetting = btn.getAttribute(
            `data-${this.prefix}-setting-select-dropdown-btn`,
          );
          //stop if same value to avoid new fetching
          const isSameVal = this.isSameValue(btnSetting, btnValue);
          if (isSameVal) return this.hideDropdown(btnSetting);
          //else, add new value to custom
          this.setSelectNewValue(btnSetting, btnValue);
          //close dropdown and change style
          this.hideDropdown(btnSetting);

          if (
            !e.target.closest("button").hasAttribute(`data-${this.prefix}-file`)
          ) {
            this.changeDropBtnStyle(btnSetting, btn);
          }
          //show / hide filter
          if (btnSetting === "instances") {
            this.hideFilterOnLocal(btn.getAttribute("data-_type"));
          }
        }
      } catch (err) {}
    });
  }

  closeAllDrop() {
    const drops = document.querySelectorAll(
      `[data-${this.prefix}-setting-select-dropdown]`,
    );
    drops.forEach((drop) => {
      drop.classList.add("hidden");
      drop.classList.remove("flex");
      document
        .querySelector(
          `svg[data-${this.prefix}-setting-select="${drop.getAttribute(
            `data-${this.prefix}-setting-select-dropdown`,
          )}"]`,
        )
        .classList.remove("rotate-180");
    });
  }

  isSameValue(btnSetting, value) {
    const selectCustom = document.querySelector(
      `[data-${this.prefix}-setting-select-text="${btnSetting}"]`,
    );
    const currVal = selectCustom.textContent;
    return currVal === value ? true : false;
  }

  setSelectNewValue(btnSetting, value) {
    const selectCustom = document.querySelector(
      `[data-${this.prefix}-setting-select="${btnSetting}"]`,
    );
    selectCustom.querySelector(
      `[data-${this.prefix}-setting-select-text]`,
    ).textContent = value;
  }

  hideDropdown(btnSetting) {
    //hide dropdown
    const dropdownEl = document.querySelector(
      `[data-${this.prefix}-setting-select-dropdown="${btnSetting}"]`,
    );
    dropdownEl.classList.add("hidden");
    dropdownEl.classList.remove("flex");
    //svg effect
    const dropdownChevron = document.querySelector(
      `svg[data-${this.prefix}-setting-select="${btnSetting}"]`,
    );
    dropdownChevron.classList.remove("rotate-180");
  }

  changeDropBtnStyle(btnSetting, selectedBtn) {
    const dropdownEl = document.querySelector(
      `[data-${this.prefix}-setting-select-dropdown="${btnSetting}"]`,
    );
    //reset dropdown btns
    const btnEls = dropdownEl.querySelectorAll("button");

    btnEls.forEach((btn) => {
      btn.classList.remove(
        "bg-primary",
        "dark:bg-primary",
        "text-gray-300",
        "text-gray-300",
      );
      btn.classList.add("bg-white", "dark:bg-slate-700", "text-gray-700");
    });
    //highlight clicked btn
    selectedBtn.classList.remove(
      "bg-white",
      "dark:bg-slate-700",
      "text-gray-700",
    );
    selectedBtn.classList.add("dark:bg-primary", "bg-primary", "text-gray-300");
  }

  toggleSelectBtn(e) {
    const attribute = e.target
      .closest("button")
      .getAttribute(`data-${this.prefix}-setting-select`);
    //toggle dropdown
    const dropdownEl = document.querySelector(
      `[data-${this.prefix}-setting-select-dropdown="${attribute}"]`,
    );
    const dropdownChevron = document.querySelector(
      `svg[data-${this.prefix}-setting-select="${attribute}"]`,
    );
    dropdownEl.classList.toggle("hidden");
    dropdownEl.classList.toggle("flex");
    dropdownChevron.classList.toggle("rotate-180");
  }

  //hide date filter on local
  hideFilterOnLocal(type) {
    if (type === "local") {
      this.hideInp(`input#from-date`);
      this.hideInp(`input#to-date`);
    }

    if (type !== "local") {
      this.showInp(`input#from-date`);
      this.showInp(`input#to-date`);
    }
  }

  showInp(selector) {
    document.querySelector(selector).closest("div").classList.add("flex");
    document.querySelector(selector).closest("div").classList.remove("hidden");
  }

  hideInp(selector) {
    document.querySelector(selector).closest("div").classList.add("hidden");
    document.querySelector(selector).closest("div").classList.remove("flex");
  }
}

class Filter {
  constructor(prefix = "configs") {
    this.prefix = prefix;
    this.container = document.querySelector(`[data-${this.prefix}-filter]`);
    this.confPathOnlyValue = "false";
    this.globalConfOnlyValue = "false";

    this.init();
  }

  init() {
    window.addEventListener("DOMContentLoaded", () => {
      this.setPathWithConfFilter();
      this.initHandler();
    });
  }

  setPathWithConfFilter() {
    // get all .conf by path
    const confs = document.querySelectorAll("[data-path*='.conf']");
    // for each, get previous path and set attribute data-path-to-a-conf
    confs.forEach((conf) => {
      const separatePath = conf.getAttribute("data-path").split("/");
      separatePath.shift();
      for (let i = 0; i < separatePath.length; i++) {
        // merge path to given index
        const path = separatePath
          .slice(0, i + 1)
          .join("/")
          .trim();
        // get element with
        const folder = document.querySelector(`[data-path="/${path}"]`);
        if (!folder) continue;
        // set attribute data-path-to-a-conf
        folder.setAttribute("data-path-to-a-conf", "");
      }
    });
  }

  initHandler() {
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
            "withconf" ||
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
            "globalconf"
        ) {
          setTimeout(() => {
            // return to root to avoid conflict, filter logic is on file.manager.js
            document
              .querySelector('[data-configs-breadcrumb-item][data-level="0"]')
              .querySelector("button")
              .click();
          }, 50);
        }
      } catch (err) {}
    });
  }
}

class ConfigsInfo {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("DOMContentLoaded", () => {
      this.totalInfo = document.querySelector("[data-info-total-conf]");
      this.globalInfo = document.querySelector("[data-info-global-conf]");
      this.totalInfo.textContent = document
        .querySelector("[data-configs-folders]")
        .querySelectorAll("[data-_type='file']").length;
      this.globalInfo.textContent = document
        .querySelector("[data-configs-folders]")
        .querySelectorAll("[data-_type='file'][data-level='2']").length;
    });
  }
}

// some configs are root only
class SetRootOnlyConf {
  constructor() {
    this.init();
    this.rootOnly = ["http", "default-http-server", "stream"];
  }

  init() {
    window.addEventListener("DOMContentLoaded", () => {
      //  remove server when config if root only
      const itemsToRemove = [];
      for (let i = 0; i < this.rootOnly.length; i++) {
        const rootName = this.rootOnly[i];
        itemsToRemove.push(
          ...document.querySelectorAll(
            `[data-path^="/etc/bunkerweb/configs/${rootName}"][data-_type="folder"][data-level="2"]`,
          ),
        );
      }
      console.log(itemsToRemove);
      itemsToRemove.forEach((item) => {
        item.remove();
      });
    });
  }
}

const setConfigsInfo = new ConfigsInfo();
const setModal = new FolderModal("configs");
const setEditor = new FolderEditor();
const setFolderNav = new FolderNav("configs");
const setDropdown = new FolderDropdown("configs");
const setFilterDropdown = new Dropdown("configs");
const setFilter = new Filter();
const setRootOnlyConf = new SetRootOnlyConf();
