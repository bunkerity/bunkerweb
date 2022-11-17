import { Checkbox } from "./utils.js";
//import AirDatepicker from "./air-datepicker/index.js";

class LogsDropdown {
  constructor(prefix = "logs") {
    this.prefix = prefix;
    this.container = document.querySelector("main");
    this.initDropdown();
    this.logListContainer = document.querySelector(`[${this.prefix}-list]`);
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
          this.hideFilterOnLocal(btn.getAttribute("_type"));
        }
      } catch (err) {}
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
    this.instanceInp = document.querySelector(
      `button[${this.prefix}-setting-select='instances']`
    );
    this.updateInp = document.querySelector("input#update-date");
    this.liveUpdateInp = document.querySelector("input#live-update");
    this.updateDelayInp = document.querySelector("input#update-delay");
    this.isLiveUpdate = false;
    this.updateDelay = 2000;
    this.lastUpdate = Math.round(Date.now() / 1000 - 86400);
    this.container = document.querySelector(`[${this.prefix}-settings]`);
    this.logListContainer = document.querySelector(`[${this.prefix}-list]`);
    this.initFetch();
    this.initLiveUpdate();
  }

  initLiveUpdate() {
    this.liveUpdateInp.addEventListener("click", (e) => {
      this.isLiveUpdate = this.liveUpdateInp.checked;
      if (this.isLiveUpdate) {
        setTimeout(() => {
          this.setLiveUpdate();
        }, this.updateDelay);
      }
    });

    this.updateDelayInp.addEventListener("input", (e) => {
      console.log(this.updateDelayInp.valueAsNumber);
      this.updateDelay = Math.round(this.updateDelayInp.valueAsNumber / 1000);
      console.log(this.updateDelay + " on change");
    });
  }

  setLiveUpdate() {
    //loop
    if (this.isLiveUpdate) {
      setTimeout(() => {
        this.setLiveUpdate();
      }, this.updateDelay);
    }
    //conditions to live update
    const btnInstance = document.querySelector(
      `[${this.prefix}-setting-select-text]`
    );
    if (btnInstance.textContent === "none" || this.lastUpdate === "") return;
    //get data
    this.getInstanceLogs(btnInstance.textContent);
  }

  goBottomList() {
    document
      .querySelector(`[${this.prefix}-list]`)
      .scrollTo(
        0,
        document.querySelector(`[${this.prefix}-list]`).scrollHeight
      );
  }

  initFetch() {
    this.container.addEventListener("click", (e) => {
      //SELECT INSTANCE
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`${this.prefix}-setting-select-dropdown-btn`) ===
          "instances"
        ) {
          const btn = e.target.closest("button");
          const btnValue = btn.getAttribute("value");
          //fetch data
          this.getInstanceLogs(btnValue);
        }
      } catch (err) {}
      //SELECT DATE
      this.updateInp.addEventListener("input", (e) => {
        this.lastUpdate = Math.round(this.updateInp.valueAsNumber / 1000);
        console.log(this.lastUpdate);
        //check if instance selected
        const btnInstance = document.querySelector(
          `[${this.prefix}-setting-select-text]`
        );
        if (btnInstance.textContent.trim() === "none") return;
        //fetch data
        this.getInstanceLogs(btnInstance.textContent);
      });
    });
  }

  async getInstanceLogs(instanceName) {
    const response = await fetch(
      `${location.href}/${instanceName}` +
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
    console.log(this.lastUpdate);
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
  }
}

class FilterLogs {
  constructor(prefix = "logs") {
    this.prefix = prefix;
    this.container = document.querySelector(`[${this.prefix}-filter]`);
    this.keyInp = document.querySelector("input#keyword");
    this.fromDateInp = document.querySelector("input#from-date");
    this.toDateInp = document.querySelector("input#to-date");
    this.lastType = "";
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
          if (this.lastType === btnValue) return;
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
    //FROM DATE
    this.fromDateInp.addEventListener("input", (e) => {
      this.filter();
    });
    //TO DATE
    this.toDateInp.addEventListener("input", (e) => {
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
    console.log("start date filtering");
    this.setFilterDate(logs);
  }

  setFilterType(logs) {
    const type = document.querySelector(
      `[${this.prefix}-setting-select-text="types"]`
    ).textContent;
    if (type === "all") return;

    for (let i = 0; i < logs.length; i++) {
      const el = logs[i];
      const typeEl = el.querySelector("[logs-type]");
      if (type !== "misc" && typeEl.textContent !== type)
        el.classList.add("hidden");
      if (
        type === "misc" &&
        typeEl.textContent !== "info" &&
        typeEl.textContent !== "message"
      )
        el.classList.add("hidden");
    }
  }

  setFilterKeyword(logs) {
    const keyword = this.keyInp.value;
    if (!keyword) return;
    for (let i = 0; i < logs.length; i++) {
      const el = logs[i];
      const content = el.querySelector("[logs-content]").textContent;
      if (!content.includes(keyword)) el.classList.add("hidden");
    }
  }

  setFilterDate(logs) {
    //get date as timestamp to check if valid
    const isValidDate = this.isDateIntervalValid(
      this.fromDateInp.valueAsNumber,
      this.toDateInp.valueAsNumber
    );
    if (!isValidDate) return console.log("date invalid");
    this.setFromDate(logs);
    this.setToDate(logs);
  }

  setToDate(logs) {
    //if from date value exist
    if (this.toDateInp.valueAsNumber) {
      //get it
      const toDate = this.toDateInp.value.split("-");
      const toMonthStr = this.monthNumToStr(toDate[1]);
      //stop if last log is after to date
      const isAfter = this.isToDateAfterLastLog();
      if (isAfter === true) return console.log("after");
      //else loop from bottom to top list
      for (let i = 0; i < logs.length; i++) {
        const el = logs[logs.length - 1 - i];
        const content = el.querySelector("[logs-content]").textContent;
        //all date format we can find on logs
        if (
          content.includes(`${toDate[0]}/${toDate[1]}/${toDate[2]}`) ||
          content.includes(`${toDate[0]}-${toDate[1]}-${toDate[2]}`) ||
          content.includes(`${toDate[0]}/${toMonthStr}/${toDate[2]}`)
        )
          break;

        el.classList.add("hidden");
      }
    }
  }

  isToDateAfterLastLog() {
    const lastLogContent = document
      .querySelector(`[${this.prefix}-list]`)
      .lastElementChild.querySelector("[logs-content]")
      .textContent.replaceAll(":", " ")
      .replaceAll("[", "[ ");

    const lastLogDate = lastLogContent.match(
      /(\d{4}([\/.-])(\d{2}|\D{3})([\/.-])\d{2} | \d{2}([\/])(\d{2}|\D{3})([\/])\d{4})/g
    );
    const lastLogStamp = new Date(lastLogDate).getTime();
    console.log(
      "last log " + lastLogStamp + " input: " + this.toDateInp.valueAsNumber
    );

    return this.toDateInp.valueAsNumber > lastLogStamp ? true : false;
  }
  setFromDate(logs) {
    //if from date value exist
    if (this.fromDateInp.valueAsNumber) {
      //get it
      const fromDate = this.fromDateInp.value.split("-");
      const fromMonthStr = this.monthNumToStr(fromDate[1]);
      //stop if first log is before date
      const isBefore = this.isFromDateBeforeFirstlog();
      if (isBefore === true) return;
      //else loop from top to bottom list
      for (let i = 0; i < logs.length; i++) {
        const el = logs[i];
        const content = el.querySelector("[logs-content]").textContent;
        //all date format we can find on logs
        if (
          content.includes(`${fromDate[0]}/${fromDate[1]}/${fromDate[2]}`) ||
          content.includes(`${fromDate[0]}-${fromDate[1]}-${fromDate[2]}`) ||
          content.includes(`${fromDate[0]}/${fromMonthStr}/${fromDate[2]}`)
        )
          break;

        el.classList.add("hidden");
      }
    }
  }

  isFromDateBeforeFirstlog() {
    const firstLogContent = document
      .querySelector(`[${this.prefix}-list]`)
      .firstElementChild.querySelector("[logs-content]").textContent;

    const firstLogDate = firstLogContent.match(
      /(\d{4}([\/.-])(\d{2}|\D{3})([\/.-])\d{2} | \d{2}([\/])(\d{2}|\D{3})([\/])\d{4})/g
    );

    const firstLogStamp = new Date(firstLogDate).getTime();
    return this.fromDateInp.valueAsNumber <= firstLogStamp ? true : false;
  }

  isDateIntervalValid(fromDate, toDate) {
    //case one date
    if (fromDate === NaN || toDate === NaN) return false;
    if (fromDate >= toDate) return false;
    return true;
  }

  monthNumToStr(month) {
    const monthStr = [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec",
    ];
    return monthStr[+month - 1];
  }
}

const setCheckbox = new Checkbox("[logs-settings]");
const dropdown = new LogsDropdown();
const setLogs = new FetchLogs();
const setFilter = new FilterLogs();
