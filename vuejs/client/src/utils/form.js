/**
  @name utils/form.js
  @description This file contains form utils that will be used in the application by default.
    This file contains functions related to form validation, form submission, and other form utils.
*/

/**
  @name useForm
  @description  This function is a composable wrapper that contains all the form utils functions.
 This function will for example look for JSON-type in the data-submit-form attribute of an element and submit the form with the data object.
*/
function useForm() {
  window.addEventListener("click", (e) => {
    if (!e.target.hasAttribute("data-submit-form")) return;
    try {
      const data = JSON.parse(e.target.getAttribute("data-submit-form"));
      useSubmitForm(data);
    } catch (e) {
      console.log(e);
    }
  });
}

/**
  @name useSubmitForm
  @description   Create programmatically a form element and submit it with the given data object of type {key: value}.
  This will create a FormData and append data arguments to it, retrieve the csrf token and send it with a regular form.
      @example
  {
    instance: "1",
    operation: "delete",
  }
  @param {object} data - Object with the form data to submit.
*/
function useSubmitForm(data) {
  // Create a form element
  const form = document.createElement("form");
  form.style.display = "none";
  form.method = "POST";
  // Retrieve csrf token form data-crfs-token
  try {
    const csrfToken = document.querySelector("[data-csrf-token]");
    if (csrfToken) {
      data.csrf_token = csrfToken.getAttribute("data-csrf-token");
    }
  } catch (e) {}
  // Add input elements with the data object
  for (const key in data) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = key;
    input.value = data[key];
    form.appendChild(input);
  }
  // Append the form to the body and submit it
  document.querySelector("body").appendChild(form);
  form.submit();
}

/**
  @name useFilter
  @description   Filter keys of an items list of objects with filters.
  @example 
  const filters = [
  {
    type: "keyword",
    value: "whitelist_ip",
    keys: ["id", "label", "name", "description", "help", "value"],
  },
  {
    type: "select",
    value: "core",
    keys: ["type"],
  },
];

  const data = [
  {
    id: "clientcache",
    stream: "no",
    name: "Client cache",
    description: "Manage caching for clients.",
},
  {
    id: "whitelist",
    stream: "no",
    name: "whitelist",
    description: "Whitelist IP",
}
];
  @param {object} plugins - Object with the plugins data.
  @param {object} filters - Object with the filters data.
*/
function useFilter(items, filters) {
  // loop on filters to determine types
  filters = removeDefaultFilters(filters);

  // Case no filters, return items
  if (filters.length === 0) return items;
  // loop on filters to determine types
  const filterTypes = [];
  filters.forEach((filter) => {
    if (!filterTypes.includes(filter.type)) filterTypes.push(filter.type);
  });

  // Deepcopy
  const data = JSON.parse(JSON.stringify(items));
  const filterData = [];
  // Loop on data
  for (let i = 0; i < data.length; i++) {
    const item = data[i];
    // Check if one filter of type "select" in filters
    if (filterTypes.includes("select") && !isItemSelect(filters, item))
      continue;

    if (filterTypes.includes("keyword") && !isItemKeyword(filters, item))
      continue;

    filterData.push(data[i]);
  }
  return filterData;
}

/**
  @name removeDefaultFilters
  @description  Remove default filters from filters array for each filter type.
  @example 
    const filters = [
  {
    type: "keyword",
    value: "",
    keys: ["id", "label", "name", "description", "help", "value"],
  },
    {
    type: "select",
    value: "all",
    keys: ["all", "core"],
  },
];
  @param filters - Array of filters to remove default filters
*/
function removeDefaultFilters(filters) {
  // Remove filters with type "select" and "all" as value
  filters = filters.filter((filter) => {
    return filter.type !== "select" || filter.value !== "all";
  });
  // Remove filters with type "keyword" and empty value
  filters = filters.filter((filter) => {
    return filter.type !== "keyword" || filter.value !== "";
  });
  return filters;
}

/**
  @name isItemKeyword
  @description  Check all items keys if at least one match with the filter value.
  @example 
    const filters = [
  {
    type: "keyword",
    value: "whitelist_ip",
    keys: ["id", "label", "name", "description", "help", "value"],
  },
];
  const items = {
    id : "test",
    label : "Test",
    name : "test",
  }
  @param filters - Array of filters
  @param items - Array of items
*/
function isItemKeyword(filters, item) {
  // Match if at least one match
  for (let j = 0; j < filters.length; j++) {
    const filter = filters[j];
    // Avoid filter cases
    const filterValue = filter.value;
    const filterType = filter.type;
    if (filterType !== "keyword" || (filterType === "keyword" && !filterValue))
      continue;

    for (let k = 0; k < filter.keys.length; k++) {
      const key = filter.keys[k];
      // Avoid if key not found in item
      if (!item[key]) continue;
      const value = item[key].replaceAll("_", " ").toLowerCase();
      // Avoid non-primitive value
      if (typeof value !== "string" && typeof value !== "number") continue;
      // Check if value contains filter value

      if (
        value &&
        value
          .toString()
          .toLowerCase()
          .includes(filter.value.replaceAll("_", " ").toLowerCase())
      ) {
        return true;
      }
    }
  }

  return false;
}

/**
  @name isItemSelect
  @description  Check all items keys if at least one match exactly the filter value.
  @example 
    const filters = [
  {
    type: "select",
    value: "core",
    keys: ["type"],
  },
];
  const items = {
    id : "test",
    label : "Test",
    name : "test",
  }
  @param filters - Array of filters
  @param items - Array of items
*/
function isItemSelect(filters, item) {
  for (let j = 0; j < filters.length; j++) {
    const filter = filters[j];
    // Avoid filter cases
    const filterValue = filter.value;
    const filterType = filter.type;
    if (
      filterType !== "select" ||
      (filterType === "select" && filterValue === "all")
    )
      continue;
    for (let k = 0; k < filter.keys.length; k++) {
      const key = filter.keys[k];
      // Avoid if key not found in item
      if (!item[key]) continue;
      const value = item[key];
      // Avoid non-primitive value
      if (typeof value !== "string" && typeof value !== "number") continue;
      // Value need to match exactly filter value
      if (value.toString().toLowerCase() === filterValue.toLowerCase()) {
        return true;
      }
    }
  }
  return false;
}

export { useForm, useFilter, isItemKeyword, isItemSelect };
