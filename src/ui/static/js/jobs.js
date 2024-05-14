import {
  Filter
} from "./utils/dashboard.js";

class Dropdown {
  constructor(prefix = "jobs") {
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


class Download {
  constructor(prefix = "jobs") {
    this.prefix = prefix;
    this.listContainer = document.querySelector(`[data-${this.prefix}-list]`);
    this.init();
  }

  init() {
    this.listContainer.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`data-${this.prefix}-download`)
        ) {
          const btnEl = e.target.closest("button");
          const pluginId = btnEl.getAttribute("data-jobs-plugin");
          const jobName = btnEl.getAttribute("data-jobs-download");
          const fileName = btnEl.getAttribute("data-jobs-file");
          this.sendFileToDL(pluginId, jobName, fileName);
        }
      } catch (err) {}
    });
  }

  async sendFileToDL(pluginId, jobName, fileName) {
    window.open(
      `${location.href}/download?plugin_id=${pluginId}&job_name=${jobName}&file_name=${fileName}`,
    );
  }
}

const setDropdown = new Dropdown("jobs");
const setDownload = new Download();

const filterContainer = document.querySelector("[data-jobs-list-container]");
if(filterContainer) {
  const noMatchEl = document.querySelector("[data-jobs-nomatch]");
  const filterEls = document.querySelectorAll(`[data-jobs-item]`);
  const keywordFilter = {
    "handler": document.querySelector("input#keyword"),
    "handlerType" : "input",
    "value" : document.querySelector("input#keyword").value,
    "filterEls": filterEls,
    "filterAtt" : "data-jobs-name",
    "filterType" : "keyword",
  };
  const successFilter = {
    "handler": document.querySelector("[data-jobs-setting-select-dropdown='success']"),
    "handlerType" : "select",
    "value" : document.querySelector("[data-jobs-setting-select-text='success']").textContent.trim().toLowerCase(),
    "filterEls": filterEls,
    "filterAtt" : "data-jobs-success",
    "filterType" : "bool",
  };
  const reloadFilter = {
    "handler": document.querySelector("[data-jobs-setting-select-dropdown='reload']"),
    "handlerType" : "select",
    "value" : document.querySelector("[data-jobs-setting-select-text='reload']").textContent.trim().toLowerCase(),
    "filterEls": filterEls,
    "filterAtt" : "data-jobs-reload",
    "filterType" : "bool",
  };
    const everyFilter = {
    "handler": document.querySelector("[data-jobs-setting-select-dropdown='every']"),
    "handlerType" : "select",
    "value" : document.querySelector("[data-jobs-setting-select-text='every']").textContent.trim().toLowerCase(),
    "filterEls": filterEls,
    "filterAtt" : "data-jobs-every",
    "filterType" : "match",
  };
  new Filter("jobs", [keywordFilter, successFilter, reloadFilter, everyFilter], filterContainer, noMatchEl);
} 
