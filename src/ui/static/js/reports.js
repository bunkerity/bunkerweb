import { CheckNoMatchFilter } from "./utils/settings.js";

class Filter {
  constructor(prefix = "reports") {
    this.prefix = prefix;
    this.keyInp = document.querySelector("input#keyword");
    this.methodValue = "all";
    this.statusValue = "all";
    this.reasonValue = "all";
    this.countryValue = "all";
    this.initHandler();
  }

  initHandler() {
    this.container =
      document.querySelector(`[data-${this.prefix}-filter]`) || null;

    if (!this.container) return;

    //METHOD HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
          "method"
        ) {
          setTimeout(() => {
            const value = document
              .querySelector(
                `[data-${this.prefix}-setting-select-text="method"]`
              )
              .textContent.trim();

            this.methodValue = value;
            //run filter
            this.filter();
          }, 10);
        }
      } catch (err) {}
    });
    //COUNTRY HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
          "country"
        ) {
          setTimeout(() => {
            const value = document
              .querySelector(
                `[data-${this.prefix}-setting-select-text="country"]`
              )
              .textContent.trim();

            this.countryValue = value;
            //run filter
            this.filter();
          }, 10);
        }
      } catch (err) {}
    });
    //STATUS HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
          "status"
        ) {
          setTimeout(() => {
            const value = document
              .querySelector(
                `[data-${this.prefix}-setting-select-text="status"]`
              )
              .textContent.trim();

            this.statusValue = value;
            //run filter
            this.filter();
          }, 10);
        }
      } catch (err) {}
    });
    // REASON HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
          "reason"
        ) {
          setTimeout(() => {
            const value = document
              .querySelector(
                `[data-${this.prefix}-setting-select-text="reason"]`
              )
              .textContent.trim();

            this.reasonValue = value;
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
    const requests = document.querySelector(
      `[data-${this.prefix}-list]`
    ).children;
    if (requests.length === 0) return;
    //reset
    for (let i = 0; i < requests.length; i++) {
      const el = requests[i];
      el.classList.remove("hidden");
    }
    //filter type
    this.setFilterMethod(requests);
    this.setFilterKeyword(requests);
    this.setFilterStatus(requests);
    this.setFilterReason(requests);
    this.setFilterCountry(requests);
  }

  setFilterMethod(requests) {
    if (this.methodValue === "all") return;
    for (let i = 0; i < requests.length; i++) {
      const el = requests[i];
      const type = this.getElAttribut(el, "method");
      if (type !== this.methodValue) el.classList.add("hidden");
    }
  }

  setFilterCountry(requests) {
    if (this.countryValue === "all") return;
    for (let i = 0; i < requests.length; i++) {
      const el = requests[i];
      const type = this.getElAttribut(el, "country");
      if (type !== this.countryValue) el.classList.add("hidden");
    }
  }

  setFilterKeyword(requests) {
    const keyword = this.keyInp.value.trim().toLowerCase();
    if (!keyword) return;
    for (let i = 0; i < requests.length; i++) {
      const el = requests[i];

      const url = this.getElAttribut(el, "url");
      const date = this.getElAttribut(el, "date");
      const ip = this.getElAttribut(el, "ip");
      const data = this.getElAttribut(el, "data");

      if (
        !url.includes(keyword) &&
        !date.includes(keyword) &&
        !ip.includes(keyword) &&
        !data.includes(keyword)
      )
        el.classList.add("hidden");
    }
  }

  setFilterStatus(requests) {
    if (this.statusValue === "all") return;
    for (let i = 0; i < requests.length; i++) {
      const el = requests[i];
      const type = this.getElAttribut(el, "status");
      if (type !== this.statusValue) el.classList.add("hidden");
    }
  }

  setFilterReason(requests) {
    if (this.reasonValue === "all") return;
    for (let i = 0; i < requests.length; i++) {
      const el = requests[i];
      const type = this.getElAttribut(el, "reason");
      if (type !== this.reasonValue) el.classList.add("hidden");
    }
  }

  getElAttribut(el, attr) {
    return el
      .querySelector(`[data-${this.prefix}-${attr}]`)
      .getAttribute(`data-${this.prefix}-${attr}`)
      .trim();
  }
}

class Dropdown {
  constructor(prefix = "reports") {
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
            `data-${this.prefix}-setting-select-dropdown-btn`
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
      `[data-${this.prefix}-setting-select-dropdown]`
    );
    drops.forEach((drop) => {
      drop.classList.add("hidden");
      drop.classList.remove("flex");
      document
        .querySelector(
          `svg[data-${this.prefix}-setting-select="${drop.getAttribute(
            `data-${this.prefix}-setting-select-dropdown`
          )}"]`
        )
        .classList.remove("rotate-180");
    });
  }

  isSameValue(btnSetting, value) {
    const selectCustom = document.querySelector(
      `[data-${this.prefix}-setting-select-text="${btnSetting}"]`
    );
    const currVal = selectCustom.textContent;
    return currVal === value ? true : false;
  }

  setSelectNewValue(btnSetting, value) {
    const selectCustom = document.querySelector(
      `[data-${this.prefix}-setting-select="${btnSetting}"]`
    );
    selectCustom.querySelector(
      `[data-${this.prefix}-setting-select-text]`
    ).textContent = value;
  }

  hideDropdown(btnSetting) {
    //hide dropdown
    const dropdownEl = document.querySelector(
      `[data-${this.prefix}-setting-select-dropdown="${btnSetting}"]`
    );
    dropdownEl.classList.add("hidden");
    dropdownEl.classList.remove("flex");
    //svg effect
    const dropdownChevron = document.querySelector(
      `svg[data-${this.prefix}-setting-select="${btnSetting}"]`
    );
    dropdownChevron.classList.remove("rotate-180");
  }

  changeDropBtnStyle(btnSetting, selectedBtn) {
    const dropdownEl = document.querySelector(
      `[data-${this.prefix}-setting-select-dropdown="${btnSetting}"]`
    );
    //reset dropdown btns
    const btnEls = dropdownEl.querySelectorAll("button");

    btnEls.forEach((btn) => {
      btn.classList.remove(
        "bg-primary",
        "dark:bg-primary",
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
    const attribute = e.target
      .closest("button")
      .getAttribute(`data-${this.prefix}-setting-select`);
    //toggle dropdown
    const dropdownEl = document.querySelector(
      `[data-${this.prefix}-setting-select-dropdown="${attribute}"]`
    );
    const dropdownChevron = document.querySelector(
      `svg[data-${this.prefix}-setting-select="${attribute}"]`
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

const setDropdown = new Dropdown();
const setFilter = new Filter();

try {
  const checkPluginKeyword = new CheckNoMatchFilter(
    document.querySelector("input#keyword"),
    "input",
    document
      .querySelector("[data-reports-list]")
      .querySelectorAll("[data-reports-item]"),
    document.querySelector("[data-reports-list-container]"),
    document.querySelector("[data-reports-nomatch]")
  );

  const checkPluginSelect = new CheckNoMatchFilter(
    document.querySelectorAll(
      "button[data-reports-setting-select-dropdown-btn]"
    ),
    "select",
    document
      .querySelector("[data-reports-list]")
      .querySelectorAll("[data-reports-item]"),
    document.querySelector("[data-reports-list-container]"),
    document.querySelector("[data-reports-nomatch]")
  );
} catch (e) {}
