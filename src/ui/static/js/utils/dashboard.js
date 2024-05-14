// filters : list of filters to be applied with this format
// [{handler : el, handlerType: "select", value: "all", filterEls: [], filterAtt: "textContent", filterType : "keyword"}]
// handler : case select, element need to be dropdown button, else direct input element
// handlerType : will determine the appropriate handler for the filter (select, input, checkbox)
// value : will determine the value of filter, need to be the default value of the filter at first
// filterEls : list of elements to be filtered
// filterAtt : value to be filtered, "textContent" will check the text content of the element, else it will check the attribute value
// filterType : type of filter, "keyword" will filter based on keyword, "match" will filter based on exact match, "bool" will filter based on boolean value ("yes", "true", "1" will be true, else false)
// noMatchEl : if exists, will be displayed when no match is found
// containerEl : container of the filter elements, case noMatchEl exists, it will be hidden when no match is found
class Filter {
constructor(prefix, filters, containerEl, noMatchEl) {
    this.prefix = prefix;
    this.filters = filters;
    this.containerEl = containerEl;
    this.noMatchEl = noMatchEl;
    this.init();
}

init() {
    this.filters.forEach((filter) => {
        // Get handler and handler type
        const handlerType = filter.handlerType;
        const handler = filter.handler;
        // Set handler base on handler type
        if(handlerType === "select") {
            this.setSelectHandler(handler);
        }
        if(handlerType === "input") {
            this.setInputHandler(handler);
        }
        if(handlerType === "checkbox") {
            this.setCheckboxHandler(handler);
        }
    });
}

setSelectHandler(handler) {
    handler.addEventListener("click", (e) => {
        try {
            const handlerName = handler.getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`);
            const value = document
            .querySelector(`[data-${this.prefix}-setting-select-text="${handlerName}"]`)
            .textContent.trim();
            this.updateValue(handlerName, value);
            this.filter();
            
        } catch(err) {}
    });
}

setInputHandler(handler) {
    handler.addEventListener("input", (e) => {
        try {
            const value = handler.value;
            this.updateValue(handler, value);
            this.filter();
        } catch(err) {}
    });

}

setCheckboxHandler(handler) {
    handler.addEventListener("change", (e) => {
        try {
            const value = handler.checked;
            this.updateValue(handler, value);
            this.filter();
        } catch(err) {}
    });
}

resetFilter() {
    this.filters.forEach((filter) => {
        const filterEls = filter.filterEls;
        filterEls.forEach((el) => {
            el.classList.remove("hidden");
        });
    });

    if(this.noMatchEl) this.noMatchEl.classList.add("hidden");

    this.containerEl.classList.remove("hidden");
}

filter() {
    // Start by resetting the filter
    this.resetFilter();
    // Then apply all filters
    let isAtLeastOneMatch = false;
    this.filters.forEach((filter) => {
        const [filterType, value, filterEls, filterAtt] = this.getFilterData(filter);

        // keyword filter means that el filter value must contains the keyword
        if(filterType === "keyword") {
            isAtLeastOneMatch = this.filterKeyword(value, filterEls, filterAtt) ? true : isAtLeastOneMatch;
        }
        // match filter means that el filter value must be equal to the filter value
        if(filterType === "match") {
            isAtLeastOneMatch = this.filterMatch(value, filterEls, filterAtt) ? true : isAtLeastOneMatch;
        }
        // bool filter means that el filter value must be equal to bool value
        if(filterType === "bool") {
            isAtLeastOneMatch = this.filterBool(value, filterEls, filterAtt) ? true : isAtLeastOneMatch;
        }
        // lower than filter means that el filter value must be lower than the filter value
        if(filterType === "lowerThan") {
            isAtLeastOneMatch = this.filterLowerThan(value, filterEls, filterAtt) ? true : isAtLeastOneMatch;
        }
        // higher than filter means that el filter value must be higher than the filter value
        if(filterType === "higherThan") {
            isAtLeastOneMatch = this.filterHigherThan(value, filterEls, filterAtt) ? true : isAtLeastOneMatch;
        }
        
    });

    // If no match is found, hide the container and display the no match element
    if(!isAtLeastOneMatch) {
        this.containerEl.classList.add("hidden");
        if(this.noMatchEl) this.noMatchEl.classList.remove("hidden");
    }

}


filterKeyword(value, filterEls, filterAtt) {
    let isAtLeastOneMatch = false;
   
    const keyword = value.trim().toLowerCase();
    if (!keyword) return false;


    for (let i = 0; i < filterEls.length; i++) {
    const el = filterEls[i];
    const elValue = this.getFilterElValue(el, filterAtt);
    if (!elValue.includes(keyword)) {
        el.classList.add("hidden");
        continue;
    }
    isAtLeastOneMatch = true;
    }

    return isAtLeastOneMatch;
}

filterMatch(value, filterEls, filterAtt) {

    if(!value || value === "all") return false;

    let isAtLeastOneMatch = false;

    for (let i = 0; i < filterEls.length; i++) {
    const el = filterEls[i];
    const elValue = this.getFilterElValue(el, filterAtt);
    if (elValue !== value) {
        el.classList.add("hidden");
        continue;
    }
    isAtLeastOneMatch = true;
    }

    return isAtLeastOneMatch;
}


filterBool(value, filterEls, filterAtt) {
    // Check if value is undefined or null
    if(value === undefined || value === null) return false;

    let isAtLeastOneMatch = false;

    for (let i = 0; i < filterEls.length; i++) {
    const el = filterEls[i];
    const elValue = this.getFilterElValue(el, filterAtt);
    const truthyValues = ["yes", "true", "1", true];
    const isValueTruthy = truthyValues.includes(elValue);
    
    if(value && isValueTruthy || !value && !isValueTruthy) {
        isAtLeastOneMatch = true;
        continue;
    }

    el.classList.add("hidden");

    }

    return isAtLeastOneMatch;
}

filterLowerThan(value, filterEls, filterAtt) {
        // Check if value is undefined or null
        if(!value) return false;

        let isAtLeastOneMatch = false;
    
        for (let i = 0; i < filterEls.length; i++) {
        const el = filterEls[i];
        const elValue = this.getFilterElValue(el, filterAtt);
        
        // check if value is not a number
        if(isNaN(elValue)) {
            el.classList.add("hidden");
            continue;
        }

        // check if int value is lower than the filter value
        if(parseInt(elValue) >= parseInt(value)) {
            el.classList.add("hidden");
            continue;
        }

        isAtLeastOneMatch = true;
    
        }
        return isAtLeastOneMatch;
    }

    filterHigherThan(value, filterEls, filterAtt) {
        // Check if value is undefined or null
        if(!value) return false;

        let isAtLeastOneMatch = false;
    
        for (let i = 0; i < filterEls.length; i++) {
        const el = filterEls[i];
        const elValue = this.getFilterElValue(el, filterAtt);
        
        // check if value is not a number
        if(isNaN(elValue)) {
            el.classList.add("hidden");
            continue;
        }

        // check if int value is lower than the filter value
        if(parseInt(elValue) <= parseInt(value)) {
            el.classList.add("hidden");
            continue;
        }

        isAtLeastOneMatch = true;
    
        }
        return isAtLeastOneMatch;
    }

    updateValue(handler, value) {
        // find on list of dict the matching handler and update the value
        const index = this.filters.findIndex((filter) => filter.handler === handler);
        this.filters[index].value = value;
    }
        

    getFilterData(filter) {
        return [filter.filterType, filter.value.trim().toLowerCase(), filter.filterEls, filter.filterAtt];
    }

    getFilterElValue(el, filterAtt) {
        return filterAtt === "textContent" ? el.textContent.trim().toLowerCase() : el.getAttribute(`data-${this.prefix}-${filterAtt}`).trim().toLowerCase();
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