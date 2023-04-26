class Checkbox {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("click", (e) => {
      //prevent default checkbox behavior
      try {
        //case a related checkbox element is clicked and checkbox is enabled
        if (
          e.target.closest("div").hasAttribute("data-checkbox-handler") &&
          !e.target
            .closest("div")
            .querySelector('input[type="checkbox"]')
            .hasAttribute("disabled")
        ) {
          //get related checkbox
          const checkboxEl = e.target
            .closest("div")
            .querySelector('input[type="checkbox"]');

          //set attribute value for new state
          checkboxEl.checked
            ? checkboxEl.setAttribute("value", "yes")
            : checkboxEl.setAttribute("value", "no");
        }
      } catch (err) {}
    });
  }
}

class Select {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("click", (e) => {
      //CASE NO BTN SELECT CLICKED
      try {
        if (!e.target.closest("button")) {
          const selectEls = document.querySelectorAll(
            "div[data-setting-select-dropdown]"
          );
          selectEls.forEach((select) => {
            select.classList.add("hidden");
            select.classList.remove("flex");
          });
          const btnEls = document.querySelectorAll(
            "button[data-setting-select]"
          );
          btnEls.forEach((btn) => {
            const dropdownChevron = btn.querySelector(
              `svg[data-setting-select]`
            );
            dropdownChevron.classList.remove("rotate-180");
          });
        }
      } catch (err) {}
      //SELECT BTN LOGIC
      try {
        if (
          e.target.closest("button").hasAttribute(`data-setting-select`) &&
          !e.target.closest("button").hasAttribute(`disabled`)
        ) {
          const btnEl = e.target.closest("button");
          this.toggleSelectBtn(btnEl);
        }
      } catch (err) {}
      //SELECT DROPDOWN BTN LOGIC
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`data-setting-select-dropdown-btn`)
        ) {
          const btn = e.target.closest(
            `button[data-setting-select-dropdown-btn]`
          );
          const btnValue = btn.getAttribute("value");

          //add new value to custom
          const selectCustom = btn
            .closest("div[data-select-container]")
            .querySelector(`button[data-setting-select]`);

          selectCustom.querySelector(`[data-setting-select-text]`).textContent =
            btnValue;
          //add selected to new value

          //change style
          const dropdownEl = btn.closest(`div[data-setting-select-dropdown]`);
          dropdownEl.classList.add("hidden");
          dropdownEl.classList.remove("flex");

          //reset dropdown btns
          const btnEls = dropdownEl.querySelectorAll("button");

          btnEls.forEach((btn) => {
            btn.classList.remove(
              "dark:bg-primary",
              "bg-primary",
              "text-gray-300"
            );
            btn.classList.add("bg-white", "dark:bg-slate-700", "text-gray-700");
          });
          //highlight clicked btn
          btn.classList.remove(
            "bg-white",
            "dark:bg-slate-700",
            "text-gray-700"
          );
          btn.classList.add("dark:bg-primary", "bg-primary", "text-gray-300");

          //close dropdown
          const dropdownChevron = selectCustom.querySelector(
            `svg[data-setting-select]`
          );
          dropdownChevron.classList.remove("rotate-180");

          //update real select element
          const realSel = btn
            .closest("div[data-setting-container]")
            .querySelector("select");
          this.updateSelected(realSel, btnValue);
        }
      } catch (err) {}
    });
  }

  updateSelected(selectEl, selectedValue) {
    const options = selectEl.querySelectorAll("option");
    //remove selected to all
    options.forEach((option) => {
      option.removeAttribute("selected");
      option.selected = false;
    });
    //select new one
    const newOption = selectEl.querySelector(
      `option[value="${selectedValue}"]`
    );
    newOption.selected = true;
    newOption.setAttribute("selected", "");
  }

  toggleSelectBtn(btn) {
    //toggle dropdown
    const dropdownEl = btn
      .closest("div")
      .querySelector(`[data-setting-select-dropdown]`);
    const dropdownChevron = btn.querySelector(`svg[data-setting-select]`);
    dropdownEl.classList.toggle("hidden");
    dropdownEl.classList.toggle("flex");
    dropdownChevron.classList.toggle("rotate-180");
  }
}

class Password {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("click", (e) => {
      try {
        if (e.target.closest("button").hasAttribute("data-setting-password")) {
          const btn = e.target.closest("button");
          const action = btn.getAttribute("data-setting-password");
          const inp = btn
            .closest("[data-setting-container]")
            .querySelector("input");
          this.setValDisplay(action, inp);
          this.hiddenBtns(btn);
          this.showOppositeBtn(btn, action);
        }
      } catch (err) {}
    });
  }

  showOppositeBtn(btnEl, action) {
    const btnEls = this.getBtns(btnEl);
    const opposite = action === "visible" ? "invisible" : "visible";

    btnEls.forEach((btn) => {
      const action = btn.getAttribute("data-setting-password");

      if (action === opposite) {
        btn.classList.add("flex");
        btn.classList.remove("hidden");
      }
    });
  }

  setValDisplay(action, inp) {
    if (action === "visible") inp.setAttribute("type", "text");
    if (action === "invisible") inp.setAttribute("type", "password");
  }

  hiddenBtns(btnEl) {
    const btnEls = this.getBtns(btnEl);

    btnEls.forEach((btn) => {
      btn.classList.add("hidden");
      btn.classList.remove("flex");
    });
  }

  getBtns(btnEl) {
    return btnEl
      .closest("[data-setting-container]")
      .querySelectorAll("button[data-setting-password]");
  }
}

class DisabledPop {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("pointerover", (e) => {
      //for checkbox and regular inputs
      if (e.target.tagName === "INPUT") {
        const el = e.target;
        this.showPopup(el, "input");
      }
      //for select custom
      if (
        e.target.tagName === "BUTTON" &&
        e.target.hasAttribute("data-setting-select")
      ) {
        const el = e.target;
        this.showPopup(el, "select");
      }
    });

    window.addEventListener("pointerout", (e) => {
      try {
        const popupEl = e.target
          .closest("div")
          .querySelector("div[data-disabled-info]");
        popupEl.remove();
      } catch (err) {}
    });
  }

  showPopup(el, type = "input") {
    if (!el.hasAttribute("disabled")) return;
    const method = el.getAttribute("data-default-method");
    const popupHTML = `
    <div data-disabled-info class="${
      type === "select" ? "translate-y-2" : ""
    } bg-blue-500 absolute right-2 rounded-lg px-2 py-1 z-20 dark:brightness-90">
    <p class="m-0 text-xs text-white dark:text-gray-100">disabled by ${method}</p>
    </div>`;
    el.insertAdjacentHTML("beforebegin", popupHTML);
  }
}

export { Checkbox, Select, Password, DisabledPop };
