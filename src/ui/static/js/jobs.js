import { CheckNoMatchFilter } from "./utils/settings.js";

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

class Filter {
  constructor(prefix = "jobs") {
    this.prefix = prefix;
    this.container =
      document.querySelector(`[data-${this.prefix}-filter]`) || null;
    this.keyInp = document.querySelector("input#keyword");
    this.successValue = "all";
    this.reloadValue = "all";
    this.everyValue = "all";
    this.initHandler();
  }

  initHandler() {
    if (!this.container) return;
    //SUCCESS HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
          "success"
        ) {
          setTimeout(() => {
            const value = document
              .querySelector(
                `[data-${this.prefix}-setting-select-text="success"]`,
              )
              .textContent.trim();

            this.successValue = value;
            //run filter
            this.filter();
          }, 10);
        }
      } catch (err) {}
    });
    //RELOAD HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
          "reload"
        ) {
          setTimeout(() => {
            const value = document
              .querySelector(
                `[data-${this.prefix}-setting-select-text="reload"]`,
              )
              .textContent.trim();

            this.reloadValue = value;
            //run filter
            this.filter();
          }, 10);
        }
      } catch (err) {}
    });
    //EVERY HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
          "every"
        ) {
          setTimeout(() => {
            const value = document
              .querySelector(
                `[data-${this.prefix}-setting-select-text="every"]`,
              )
              .textContent.trim();

            this.everyValue = value;
            //run filter
            this.filter();
          }, 10);
        }
      } catch (err) {}
    });
    //KEYWORD HANDLER
    this.keyInp.addEventListener("input", (e) => {
      this.filter();
    });
  }

  filter() {
    const jobs = document.querySelector(`[data-${this.prefix}-list]`).children;
    if (jobs.length === 0) return;
    //reset
    for (let i = 0; i < jobs.length; i++) {
      const el = jobs[i];
      el.classList.remove("hidden");
    }
    //filter type
    this.setFilterSuccess(jobs);
    this.setFilterEvery(jobs);
    this.setFilterReload(jobs);
    this.setFilterKeyword(jobs);
  }

  setFilterEvery(jobs) {
    if (this.everyValue === "all") return;
    for (let i = 0; i < jobs.length; i++) {
      const el = jobs[i];
      const type = el
        .querySelector(`[data-${this.prefix}-every]`)
        .getAttribute(`data-${this.prefix}-every`)
        .trim();
      if (type !== this.everyValue) el.classList.add("hidden");
    }
  }

  setFilterSuccess(jobs) {
    if (this.successValue === "all") return;
    for (let i = 0; i < jobs.length; i++) {
      const el = jobs[i];
      const type = el
        .querySelector(`[data-${this.prefix}-success]`)
        .getAttribute(`data-${this.prefix}-success`)
        .trim();
      if (type !== this.successValue) el.classList.add("hidden");
    }
  }

  setFilterReload(jobs) {
    if (this.reloadValue === "all") return;
    for (let i = 0; i < jobs.length; i++) {
      const el = jobs[i];
      const type = el
        .querySelector(`[data-${this.prefix}-reload]`)
        .getAttribute(`data-${this.prefix}-reload`)
        .trim();
      if (type !== this.reloadValue) el.classList.add("hidden");
    }
  }

  setFilterKeyword(jobs) {
    const keyword = this.keyInp.value.trim().toLowerCase();
    if (!keyword) return;
    for (let i = 0; i < jobs.length; i++) {
      const el = jobs[i];
      const name = el
        .querySelector(`[data-${this.prefix}-name]`)
        .textContent.trim()
        .toLowerCase();
      const date = el
        .querySelector(`[data-${this.prefix}-last_run]`)
        .textContent.trim()
        .toLowerCase();
      const every = el
        .querySelector(`[data-${this.prefix}-every]`)
        .textContent.trim()
        .toLowerCase();

      if (
        !name.includes(keyword) &&
        !date.includes(keyword) &&
        !every.includes(keyword)
      )
        el.classList.add("hidden");
    }
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
const setFilter = new Filter("jobs");
const setDownload = new Download();

const checkPluginKeyword = new CheckNoMatchFilter(
  document.querySelector("input#keyword"),
  "input",
  document
    .querySelector("[data-jobs-list]")
    .querySelectorAll("[data-jobs-item]"),
  document.querySelector("[data-jobs-list-container]"),
  document.querySelector("[data-jobs-nomatch]"),
);

const checkPluginSelect = new CheckNoMatchFilter(
  document.querySelectorAll("button[data-jobs-setting-select-dropdown-btn]"),
  "select",
  document
    .querySelector("[data-jobs-list]")
    .querySelectorAll("[data-jobs-item]"),
  document.querySelector("[data-jobs-list-container]"),
  document.querySelector("[data-jobs-nomatch]"),
);
