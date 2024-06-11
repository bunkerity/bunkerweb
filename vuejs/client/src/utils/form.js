/**
  @name utils/form.js
  @description This file contains form utils that will be used in the application by default.
    This file contains functions related to form validation, form submission, and other form utils.
*/

/**
  @name useForm
  @description  This function is a composable wrapper that contains all the form utils functions.
 This function will for example look for elements with data-submit-form attribute and submit the form with the data attributes.
*/
function useForm() {
  window.addEventListener("click", (e) => {
    if (!e.target.hasAttribute("data-submit-form")) return;
    const data = useGetFormDataAttr(e.target);
    useSubmitForm(data);
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
  console.log(form);
  form.submit();
}

/**
  @name useGetFormDataAttr
  @description Get the form data store on attributes of the element.
  Format is data-form-<key>="<value>"
  @example document.querySelector("[data-submit-form]")
  @param {DOMElement} el - Element to get the data attributes.
*/
function useGetFormDataAttr(el) {
  const data = {};
  const attributes = el.attributes;
  for (let i = 0; i < attributes.length; i++) {
    if (attributes[i].name.includes("data-form-")) {
      const key = attributes[i].name.replace("data-form-", "");
      data[key] = attributes[i].value;
    }
  }
  return data;
}

/**
  @name useFilterSettingsAdvanced
  @description   Filter advanced settings templates based on filters object.
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

  const plugins = [
  {
    id: "clientcache",
    stream: "no",
    name: "Client cache",
    description: "Manage caching for clients.",
    version: "1.0",
    type: "core",
    method: "manual",
    page: false,
    settings: {
      USE_CLIENT_CACHE: {
        context: "multisite",
        default: "no",
        help: "Tell client to store locally static files.",
        id: "use-client-cache-default",
        label: "Use client cache",
        regex: "^(yes|no)$",
        type: "check",
        containerClass: "z-3",
        pattern: "^(yes|no)$",
        inpType: "checkbox",
        name: "Use client cache",
        columns: {
          pc: 4,
          tablet: 6,
          mobile: 12,
        },
        disabled: true,
        value: "yes",
        popovers: [
          {
            iconColor: "info",
            iconName: "info",
            text: "Tell client to store locally static files.",
          },
          {
            iconColor: "orange",
            iconName: "disk",
            text: "inp_popover_multisite",
          },
        ],
      },
    },
    checksum: null,
  },
];
  @param {object} plugins - Object with the plugins data.
  @param {object} filters - Object with the filters data.
*/
function useFilterPluginsAdvanced(plugins, filters) {
  // loop on filters to determine types
  filters = removeDefaultFilters(filters);

  // Case no filters, return plugins
  if (filters.length === 0) return plugins;

  const filterTypes = [];
  filters.forEach((filter) => {
    if (!filterTypes.includes(filter.type)) filterTypes.push(filter.type);
  });

  // Deepcopy
  const data = JSON.parse(JSON.stringify(plugins));
  const filterData = [];
  // Loop on data
  for (let i = 0; i < data.length; i++) {
    // Prepare data
    const items = [];
    const plugin = JSON.parse(JSON.stringify(data[i]));
    // Get SETTING_NAME as id
    const settings = plugin.settings;
    for (const key in settings) {
      items.push({ id: key });
      items.push(settings[key]);
    }
    // Get settings and remove settings from plugin to avoid duplicate
    delete plugin["settings"];
    items.push(plugin);

    // Check if one filter of type "select" in filters
    if (filterTypes.includes("select") && !isMatchingSelect(filters, items))
      continue;

    if (filterTypes.includes("keyword") && !isMatchingKeyword(filters, items))
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
  @name isMatchingKeyword
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
function isMatchingKeyword(filters, items) {
  // Match if at least one match
  let atLeastOneMatch = false;
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    for (let j = 0; j < filters.length; j++) {
      const filter = filters[j];
      // Avoid filter cases
      const filterValue = filter.value;
      const filterType = filter.type;
      if (filterType !== "keyword") continue;

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
            .includes(filterValue.replaceAll("_", " ").toLowerCase())
        ) {
          atLeastOneMatch = true;
          break;
        }
      }
    }
  }

  return atLeastOneMatch;
}

/**
  @name isMatchingSelect
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
function isMatchingSelect(filters, items) {
  let atLeastOneMatch = false;
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    for (let j = 0; j < filters.length; j++) {
      const filter = filters[j];
      // Avoid filter cases
      const filterValue = filter.value;
      const filterType = filter.type;
      if (filterType !== "select") continue;

      for (let k = 0; k < filter.keys.length; k++) {
        const key = filter.keys[k];
        // Avoid if key not found in item
        if (!item[key]) continue;
        const value = item[key];
        // Avoid non-primitive value
        if (typeof value !== "string" && typeof value !== "number") continue;
        // Value need to match exactly filter value
        if (value.toString().toLowerCase() === filterValue.toLowerCase()) {
          atLeastOneMatch = true;
          break;
        }
      }
    }
  }
  return atLeastOneMatch;
}

export { useForm, useFilterPluginsAdvanced };
