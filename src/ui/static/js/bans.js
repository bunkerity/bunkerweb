class Filter {
  constructor(prefix = "bans") {
    this.prefix = prefix;
    this.container = document.querySelector(`[data-${this.prefix}-filter]`);
    this.keyInp = document.querySelector("input#keyword");
    this.termValue = "all";
    this.reasonValue = "all";
    this.initHandler();
  }

  initHandler() {
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
                `[data-${this.prefix}-setting-select-text="reason"]`,
              )
              .textContent.trim();

            this.reasonValue = value;
            //run filter
            this.filter();
          }, 10);
        }
      } catch (err) {}
    });
    // TERM HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
          "term"
        ) {
          setTimeout(() => {
            const value = document
              .querySelector(`[data-${this.prefix}-setting-select-text="term"]`)
              .textContent.trim();

            this.termValue = value;
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
    const bans = document.querySelector(`[data-${this.prefix}-list]`).children;
    if (bans.length === 0) return;
    //reset
    for (let i = 0; i < bans.length; i++) {
      const el = bans[i];
      el.classList.remove("hidden");
    }
    //filter type
    this.setFilterKeyword(bans);
    this.setFilterReason(bans);
    this.setFilterTerm(bans);
  }

  setFilterKeyword(bans) {
    const keyword = this.keyInp.value.trim().toLowerCase();
    if (!keyword) return;
    for (let i = 0; i < bans.length; i++) {
      const el = bans[i];

      const ip = this.getElAttribut(el, "ip");
      const banStart = this.getElAttribut(el, "ban_sart");
      const banEnd = this.getElAttribut(el, "ban_end");
      const remain = this.getElAttribut(el, "remain");

      if (
        !ip.includes(keyword) &&
        !banStart.includes(keyword) &&
        !banEnd.includes(keyword) &&
        !remain.includes(keyword)
      )
        el.classList.add("hidden");
    }
  }

  setFilterTerm(bans) {
    if (this.termValue === "all") return;
    for (let i = 0; i < bans.length; i++) {
      const el = bans[i];
      const type = this.getElAttribut(el, "term");
      if (type !== this.termValue) el.classList.add("hidden");
    }
  }

  setFilterReason(bans) {
    if (this.reasonValue === "all") return;
    for (let i = 0; i < bans.length; i++) {
      const el = bans[i];
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
  constructor(prefix = "bans") {
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

class Unban {
  constructor(prefix = "bans") {
    this.prefix = prefix;
    this.container = document.querySelector("main");
    this.listEl = document.querySelector(`[data-${this.prefix}-list]`);
    this.unbanForm = document.querySelector("#unban-items");
    this.unbanBtn = document.querySelector(`button[data-unban-btn]`);
    this.unbanInp = document.querySelector(`input[data-unban-inp]`);
    this.init();
  }

  init() {
    //  Look if an item is select to enable unban button
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target.closest("div").hasAttribute(`data-${this.prefix}-ban-select`)
        ) {
          // timeout to wait for select value to change
          setTimeout(() => {
            // Check if at least one item is selected
            const selected = this.listEl.querySelectorAll(
              `input[data-checked="true"]`,
            );

            // Case true, enable unban button
            if (selected.length > 0) {
              this.unbanBtn.removeAttribute("disabled");
            }

            // Case false, disable unban button
            if (selected.length === 0) {
              this.unbanBtn.setAttribute("disabled", "");
            }
          }, 100);
        }
      } catch (err) {}
    });
    // unban button
    this.unbanForm.addEventListener("submit", (e) => {
      e.preventDefault();
      if (this.unbanBtn.hasAttribute("disabled")) return;
      // Get all selected items
      const selected = this.listEl.querySelectorAll(
        `input[data-checked="true"]`,
      );
      const getDatas = [];
      selected.forEach((el) => {
        const data = el
          .closest(`li[data-${this.prefix}-list-item]`)
          .getAttribute(`data-${this.prefix}-list-item`);
        getDatas.push(data);
      });
      this.unbanInp.value = JSON.stringify(getDatas);
      this.unbanInp.setAttribute("value", JSON.stringify(getDatas));
      this.unbanForm.submit();
    });
  }
}

const setDropdown = new Dropdown();
const setFilter = new Filter();
const setUnban = new Unban();
