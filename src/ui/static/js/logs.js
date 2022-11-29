import { Checkbox } from "./utils/form.js";
import Datepicker from "./datepicker/datepicker.js";

class Dropdown {
  constructor(prefix = "logs") {
    this.prefix = prefix;
    this.container = document.querySelector("main");
    this.initDropdown();
  }

  initDropdown() {
    this.container.addEventListener("click", (e) => {
      //SELECT BTN LOGIC
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`${this.prefix}-setting-select`) &&
          !e.target.closest("button").hasAttribute(`disabled`)
        ) {
          const btnName = e.target
            .closest("button")
            .getAttribute(`${this.prefix}-setting-select`);
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
            .hasAttribute(`${this.prefix}-setting-select-dropdown-btn`)
        ) {
          const btn = e.target.closest("button");
          const btnValue = btn.getAttribute("value");
          const btnSetting = btn.getAttribute(
            `${this.prefix}-setting-select-dropdown-btn`
          );
          //stop if same value to avoid new fetching
          const isSameVal = this.isSameValue(btnSetting, btnValue);
          if (isSameVal) return this.hideDropdown(btnSetting);
          //else, add new value to custom
          this.setSelectNewValue(btnSetting, btnValue);
          //close dropdown and change style
          this.hideDropdown(btnSetting);
          this.changeDropBtnStyle(btnSetting, btn);
          //show / hide filter
          if (btnSetting === "instances") {
            this.hideFilterOnLocal(btn.getAttribute("_type"));
          }
        }
      } catch (err) {}
    });
  }

  closeAllDrop() {
    const drops = document.querySelectorAll(
      `[${this.prefix}-setting-select-dropdown]`
    );
    drops.forEach((drop) => {
      drop.classList.add("hidden");
      drop.classList.remove("flex");
      document
        .querySelector(
          `svg[${this.prefix}-setting-select="${drop.getAttribute(
            `${this.prefix}-setting-select-dropdown`
          )}"]`
        )
        .classList.remove("rotate-180");
    });
  }

  isSameValue(btnSetting, value) {
    const selectCustom = document.querySelector(
      `[${this.prefix}-setting-select-text="${btnSetting}"]`
    );
    const currVal = selectCustom.textContent;
    return currVal === value ? true : false;
  }

  setSelectNewValue(btnSetting, value) {
    const selectCustom = document.querySelector(
      `[${this.prefix}-setting-select="${btnSetting}"]`
    );
    selectCustom.querySelector(
      `[${this.prefix}-setting-select-text]`
    ).textContent = value;
  }

  hideDropdown(btnSetting) {
    //hide dropdown
    const dropdownEl = document.querySelector(
      `[${this.prefix}-setting-select-dropdown="${btnSetting}"]`
    );
    dropdownEl.classList.add("hidden");
    dropdownEl.classList.remove("flex");
    //svg effect
    const dropdownChevron = document.querySelector(
      `svg[${this.prefix}-setting-select="${btnSetting}"]`
    );
    dropdownChevron.classList.remove("rotate-180");
  }

  changeDropBtnStyle(btnSetting, selectedBtn) {
    const dropdownEl = document.querySelector(
      `[${this.prefix}-setting-select-dropdown="${btnSetting}"]`
    );
    //reset dropdown btns
    const btnEls = dropdownEl.querySelectorAll("button");

    btnEls.forEach((btn) => {
      btn.classList.remove(
        "dark:bg-primary",
        "bg-primary",
        "bg-primary",
        "text-gray-300",
        "text-gray-300"
      );
      btn.classList.add("bg-white", "dark:bg-slate-700", "text-gray-700");
    });
    //highlight clicked btn
    selectedBtn.classList.remove(
      "bg-white",
      "dark:bg-slate-700",
      "text-gray-700"
    );
    selectedBtn.classList.add("dark:bg-primary", "bg-primary", "text-gray-300");
  }

  toggleSelectBtn(e) {
    const attribut = e.target
      .closest("button")
      .getAttribute(`${this.prefix}-setting-select`);
    //toggle dropdown
    const dropdownEl = document.querySelector(
      `[${this.prefix}-setting-select-dropdown="${attribut}"]`
    );
    const dropdownChevron = document.querySelector(
      `svg[${this.prefix}-setting-select="${attribut}"]`
    );
    dropdownEl.classList.toggle("hidden");
    dropdownEl.classList.toggle("flex");
    dropdownChevron.classList.toggle("rotate-180");
  }

  //hide date filter on local
  hideFilterOnLocal(type) {
    console.log(type);
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

class FetchLogs {
  constructor(prefix = "logs") {
    this.prefix = prefix;
    this.instance = document.querySelector(
      `[${this.prefix}-setting-select-text="instances"]`
    );
    this.instanceName = "";
    this.updateInp = document.querySelector("input#update-date");
    this.liveUpdateInp = document.querySelector("input#live-update");
    this.updateDelayInp = document.querySelector("input#update-delay");
    this.fromDateInp = document.querySelector("input#from-date");
    this.toDateInp = document.querySelector("input#to-date");
    this.fromDate = "";
    this.toDate = "";
    this.isLiveUpdate = false;
    this.updateDelay = 2000;
    this.lastUpdate = Date.now() - 86400000;
    this.container = document.querySelector(`[${this.prefix}-settings]`);
    this.logListContainer = document.querySelector(`[${this.prefix}-list]`);
    this.submitSettings = document.querySelector("button#submit-settings");
    this.init();
  }

  init() {
    this.submitSettings.addEventListener("click", (e) => {
      //remove prev logs
      this.logListContainer.textContent = "";
      //wait if live update previously
      if (this.isLiveUpdate && !this.toDate) {
        setTimeout(() => {
          const isSettings = this.getSettings();
          return isSettings ? this.getLogsFromToDate() : "";
        }, this.updateDelay);
      } else {
        const isSettings = this.getSettings();
        return isSettings ? this.getLogsFromToDate() : "";
      }
    });
    //disabled/enabled filed logic
    this.toDateInp.addEventListener("input", (e) => {
      this.toDateInp.value
        ? this.updateDelayInp.setAttribute("disabled", "")
        : this.updateDelayInp.removeAttribute("disabled");
      this.toDateInp.value
        ? this.liveUpdateInp.setAttribute("disabled", "")
        : this.liveUpdateInp.removeAttribute("disabled");
    });

    this.updateDelayInp.addEventListener("input", (e) => {
      this.updateDelayInp.value
        ? this.toDateInp.setAttribute("disabled", "")
        : this.toDateInp.removeAttribute("disabled");
    });

    this.liveUpdateInp.addEventListener("input", (e) => {
      this.liveUpdateInp.checked
        ? this.toDateInp.setAttribute("disabled", "")
        : this.toDateInp.removeAttribute("disabled");
    });
  }

  getSettings() {
    //get settings
    //check valid instance name
    this.instanceName = this.instance.textContent;
    if (!this.instanceName || this.instanceName.trim() === "none") return false;
    //if a date value exist, check if is a timestamp
    if (this.fromDateInp.value && isNaN(Date.parse(this.fromDateInp.value)))
      return false;
    if (this.toDateInp.value && isNaN(Date.parse(this.toDateInp.value)))
      return false;
    //check valid date
    this.fromDate = Date.parse(this.fromDateInp.value)
      ? Date.parse(this.fromDateInp.value)
      : Date.now() - 86400000;
    this.toDate = Date.parse(this.toDateInp.value)
      ? Date.parse(this.toDateInp.value)
      : false;
    this.updateDelay =
      this.updateDelayInp.value * 1000 ? this.updateDelayInp.value : 2000;
    this.isLiveUpdate = this.liveUpdateInp.checked;
    return true;
  }

  goBottomList() {
    document
      .querySelector(`[${this.prefix}-list]`)
      .scrollTo(
        0,
        document.querySelector(`[${this.prefix}-list]`).scrollHeight
      );
  }

  async getLogsFromToDate() {
    console.log(this.fromDate, this.toDate);
    let response;
    if (this.toDate) {
      response = await fetch(
        `${location.href}/${this.instanceName}?from_date=${this.fromDate}&to_date=${this.toDate}`
      );
    }

    if (!this.toDate) {
      response = await fetch(
        `${location.href}/${this.instanceName}?from_date=${this.fromDate}`
      );
    }

    if (response.status === 200) {
      const res = await response.json();
      //last update
      return await this.showLogs(res);
    } else {
      console.log(`Error: ${response.status}`);
    }
    return null;
  }

  async getLogsSinceLastUpdate() {
    const response = await fetch(
      `${location.href}/${this.instanceName}` +
        (this.lastUpdate ? `?last_update=${this.lastUpdate}` : "")
    );

    if (response.status === 200) {
      const res = await response.json();
      //last update
      return await this.showLogs(res);
    } else {
      console.log(`Error: ${response.status}`);
    }
    return null;
  }

  async showLogs(res) {
    this.lastUpdate = res.last_update;
    res.logs.forEach((log) => {
      //container
      const logContainer = document.createElement("li");
      logContainer.className =
        "grid grid-cols-12 border-b border-gray-300 py-2";
      //type
      const typeEl = document.createElement("p");
      typeEl.className =
        "dark:text-gray-400 dark:opacity-80 text-sm col-span-3 m-0";
      typeEl.textContent = log.type;
      typeEl.setAttribute("logs-type", "");
      logContainer.appendChild(typeEl);
      //content
      const contentEl = document.createElement("p");
      contentEl.className =
        "dark:text-gray-400 dark:opacity-80 text-sm col-span-9 m-0";
      contentEl.textContent = log.content;
      contentEl.setAttribute("logs-content", "");
      logContainer.appendChild(contentEl);
      //show on DOM
      this.logListContainer.appendChild(logContainer);
    });

    setTimeout(() => {
      this.goBottomList();
    }, 100);
    //loop if no to date and live update true
    if (this.isLiveUpdate && !this.toDate) {
      setTimeout(() => {
        this.getLogsSinceLastUpdate();
      }, this.updateDelay);
    }
  }
}

class Filter {
  constructor(prefix = "logs") {
    this.prefix = prefix;
    this.container = document.querySelector(`[${this.prefix}-filter]`);
    this.keyInp = document.querySelector("input#keyword");
    this.lastType = "all";
    this.initHandler();
  }

  initHandler() {
    //TYPE HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`${this.prefix}-setting-select-dropdown-btn`) ===
          "types"
        ) {
          const btn = e.target.closest("button");
          const btnValue = btn.getAttribute("value");
          const btnSetting = btn.getAttribute(
            `${this.prefix}-setting-select-dropdown-btn`
          );

          this.lastType = btnValue;
          //run filter
          this.filter();
        }
      } catch (err) {}
    });
    //KEYWORD HANDLER
    this.keyInp.addEventListener("input", (e) => {
      this.filter();
    });
  }

  filter() {
    const logs = document.querySelector(`[${this.prefix}-list]`).children;
    if (logs.length === 0) return;
    //reset
    for (let i = 0; i < logs.length; i++) {
      const el = logs[i];
      el.classList.remove("hidden");
    }
    //filter type
    this.setFilterType(logs);
    this.setFilterKeyword(logs);
  }

  setFilterType(logs) {
    if (this.lastType === "all") return;

    for (let i = 0; i < logs.length; i++) {
      const el = logs[i];
      const typeEl = el.querySelector("[logs-type]");
      if (this.lastType !== "misc" && typeEl.textContent !== this.lastType)
        el.classList.add("hidden");
      if (
        this.lastType === "misc" &&
        typeEl.textContent !== "info" &&
        typeEl.textContent !== "message"
      )
        el.classList.add("hidden");
    }
  }

  setFilterKeyword(logs) {
    const keyword = this.keyInp.value.trim().toLowerCase();
    if (!keyword) return;
    for (let i = 0; i < logs.length; i++) {
      const el = logs[i];
      const content = el
        .querySelector("[logs-content]")
        .textContent.trim()
        .toLowerCase();
      if (!content.includes(keyword)) el.classList.add("hidden");
    }
  }
}

class LogsDate {
  constructor(el, options = {}) {
    this.datepicker = new Datepicker(el, options);
    this.container = document.querySelector("[logs-settings]");
  }
}

const setCheckbox = new Checkbox("[logs-settings]");
const dropdown = new Dropdown("logs");
const setLogs = new FetchLogs();
const setFilter = new Filter("logs");
const fromDatepicker = new LogsDate(document.querySelector("input#from-date"));
const toDatepicker = new LogsDate(document.querySelector("input#to-date"));
