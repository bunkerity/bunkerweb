class Checkbox {
  constructor(container) {
    this.container = container;
    this.checkContainer = document.querySelector(`${this.container}`);
    this.init();
  }

  init() {
    this.checkContainer.addEventListener("click", (e) => {
      //checkbox click
      try {
        if (
          e.target.closest("div").hasAttribute("checkbox-handler") &&
          !e.target
            .closest("div")
            .querySelector('input[type="checkbox"]')
            .hasAttribute("disabled")
        ) {
          //change DOM
          const checkboxEl = e.target
            .closest("div")
            .querySelector('input[type="checkbox"]');
          checkboxEl.checked
            ? checkboxEl.setAttribute("value", "yes")
            : checkboxEl.setAttribute("value", "no");
        }
      } catch (err) {}
      //nested elements click
      try {
        if (
          e.target.closest("svg").hasAttribute("checkbox-handler") &&
          !e.target
            .closest("div")
            .querySelector('input[type="checkbox"]')
            .hasAttribute("disabled")
        ) {
          e.target
            .closest("div")
            .querySelector('input[type="checkbox"]')
            .click();
        }
      } catch (err) {}
    });
  }
}

class Select {
  constructor(container, prefixAtt) {
    this.prefix = prefixAtt;
    this.container = container;
    this.SelectContainer = document.querySelector(`${this.container}`);
    this.init();
  }

  init() {
    this.SelectContainer.addEventListener("click", (e) => {
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
          //add new value to custom
          const selectCustom = document.querySelector(
            `[${this.prefix}-setting-select="${btnSetting}"]`
          );
          selectCustom.querySelector(
            `[${this.prefix}-setting-select-text]`
          ).textContent = btnValue;
          //add selected to new value

          //change style
          const dropdownEl = document.querySelector(
            `[${this.prefix}-setting-select-dropdown="${btnSetting}"]`
          );
          dropdownEl.classList.add("hidden");
          dropdownEl.classList.remove("flex");

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
          btn.classList.remove(
            "bg-white",
            "dark:bg-slate-700",
            "text-gray-700"
          );
          btn.classList.add("dark:bg-primary", "bg-primary", "text-gray-300");

          //close dropdown
          const dropdownChevron = document.querySelector(
            `svg[${this.prefix}-setting-select="${btnSetting}"]`
          );
          dropdownChevron.classList.remove("rotate-180");

          //update real select element
          this.updateSelected(
            document.querySelector(
              `[${this.prefix}-setting-select-default="${btnSetting}"]`
            ),
            btnValue
          );
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
}

export { Checkbox, Select };
