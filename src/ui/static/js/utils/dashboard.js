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
constructor(prefix, filters, containerEl = null, noMatchEl = null) {
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
            if(!e.target.closest("button").hasAttribute(`data-${this.prefix}-setting-select-dropdown-btn`)) return;
            const value = e.target.closest("button").getAttribute('value');
            this.updateValue(handler, value);
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
    if(this.containerEl)this.containerEl.classList.remove("hidden");
}

filter() {
    // Start by resetting the filter
    this.resetFilter();
    // Then apply all filters

    this.filters.forEach((filter) => {
        const [filterType, value, filterEls, filterAtt] = this.getFilterData(filter);
        // keyword filter means that el filter value must contains the keyword
        if(filterType === "keyword") {
            this.filterKeyword(value, filterEls, filterAtt);
        }
        // match filter means that el filter value must be equal to the filter value
        if(filterType === "match") {
            this.filterMatch(value, filterEls, filterAtt);
        }
        // bool filter means that el filter value must be equal to bool value
        if(filterType === "bool") {
            this.filterBool(value, filterEls, filterAtt);
        }
        // lower than filter means that el filter value must be lower than the filter value
        if(filterType === "lowerThan") {
            this.filterLowerThan(value, filterEls, filterAtt);
        }
        // higher than filter means that el filter value must be higher than the filter value
        if(filterType === "higherThan") {
            this.filterHigherThan(value, filterEls, filterAtt);
        }
        
    });
    // If no match is found, hide the container and display the no match element
    if(!this.isAtLeastOneMatch()) {
        console.log("run")
        if(this.containerEl) this.containerEl.classList.add("hidden");
        if(this.noMatchEl) this.noMatchEl.classList.remove("hidden");
    }
}

filterKeyword(value, filterEls, filterAtt) {
    const keyword = value.trim().toLowerCase();

    if (!keyword) return;

    for (let i = 0; i < filterEls.length; i++) {
    const el = filterEls[i];
    const elValue = this.getFilterElValue(el, filterAtt);
    if (!elValue.includes(keyword)) {
        el.classList.add("hidden");
        continue;
    }
    }

    return;
}

filterMatch(value, filterEls, filterAtt) {
    if(!value || value === "all") return;

    for (let i = 0; i < filterEls.length; i++) {
    const el = filterEls[i];
    const elValue = this.getFilterElValue(el, filterAtt);
    if (elValue !== value) {
        el.classList.add("hidden");
        continue;
    }
    }

    return;
}


filterBool(value, filterEls, filterAtt) {
    console.log(value, filterEls, filterAtt)
    // Check if value is undefined or null
    if(value === undefined || value === null || value === "all") return;

    for (let i = 0; i < filterEls.length; i++) {
    const el = filterEls[i];
    const elValue = this.getFilterElValue(el, filterAtt);
    const truthyValues = ["yes", "true", "1", true];
    const isValueElTruthy = truthyValues.includes(elValue);
    const isValueTruthy = truthyValues.includes(value);
    console.log(value, isValueTruthy)
    if(isValueElTruthy === isValueTruthy) {
        continue;
    }

    el.classList.add("hidden");

    }

    return ;
}

filterLowerThan(value, filterEls, filterAtt) {
        // Check if value is undefined or null
        if(!value || value === 'all') return;

    
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
    
        }
        return;
    }

    filterHigherThan(value, filterEls, filterAtt) {
        // Check if value is undefined or null
        if(!value || value === 'all') return;
    
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

    
        }
        return;
    }

    isAtLeastOneMatch() {
        // loop on each filterEls and check if at least one is not hidden
        let isOneMatch = false;
        for(let i = 0; i < this.filters.length; i++) {
            const filter = this.filters[i];
            const filterEls = filter.filterEls;
            filterEls.forEach((el) => {
                if(!el.classList.contains("hidden")) {
                    isOneMatch = true;
                    return;
                }
            });
            if(isOneMatch) break;
        }

        return isOneMatch;
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
        return filterAtt === "textContent" ? el.textContent.trim().toLowerCase() : el.getAttribute(filterAtt).trim().toLowerCase();
    }

}

class Dropdown {
    constructor() 
    {
        this.init();
    }

    init(){

    }
}

export { Filter, Dropdown };