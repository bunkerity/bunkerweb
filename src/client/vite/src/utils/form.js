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
  // Append to be able to submit
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
  @param {array} filters - Array with the filters data.
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
      if (
        value.toString().toLowerCase().trim() !==
        filterValue.toString().toLowerCase().trim()
      ) {
        return false;
      }
    }
  }
  return true;
}

/**
  @name useCheckPluginsValidity
  @description  Check all items keys if at least one match exactly the filter value.
  @example 
    const template = [
  {
    name: "test",
    settings: {
      test: {
        required: true,
        value: "",
        pattern: "^[a-zA-Z0-9]*$",
      },
    },
  },
  @param template - Template with plugins list and detail settings
*/
function useCheckPluginsValidity(template) {
  let isRegErr = false;
  let isReqErr = false;
  let settingErr = "";
  let pluginErr = "";
  let settingNameErr = "";
  let id = 0;

  template.forEach((plugin, index) => {
    id = index;
    for (const [key, value] of Object.entries(plugin.settings)) {
      if (value.required && !value.value) {
        isReqErr = true;
        settingErr = key;
        settingNameErr = value.name;
        pluginErr = plugin.name;
        break;
      }
      if (value.pattern && value.value) {
        const regex = new RegExp(value.pattern);
        if (!regex.test(value.value)) {
          isRegErr = true;
          settingErr = key;
          settingNameErr = value.name;
          pluginErr = plugin.name;
          break;
        }
      }
    }
  });

  return [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr, id];
}

/**
  @name useListenTempFields
  @description  This will add an handler to all needed event listeners to listen to input, select... fields in order to update the template settings.
  @example 
  function hander(e) {
    // some code before calling useUpdateTemp
    if (!e.target.closest("[data-advanced-form-plugin]")) return;
    useUpdateTemp(e, data.base);
  }
  @param handler - Callback function to call when event is triggered. This is usually an intermediate function that will call the useUpdateTemp function.
*/
function useListenTempFields(handler) {
  window.addEventListener("input", handler);
  window.addEventListener("change", handler);
  window.addEventListener("click", handler);
}

/**
  @name useUnlistenTempFields
  @description  This will stop listening to input, select... fields. Performance optimization and avoid duplicate calls conflicts.
  @example 
  function hander(e) {
    // some code before calling useUpdateTemp
    if (!e.target.closest("[data-advanced-form-plugin]")) return;
    useUpdateTemp(e, data.base);
  }
  @param handler - Callback function to call when event is triggered. Need to be the same function as the one passed to useListenTempFields.
*/
function useUnlistenTempFields(handler) {
  window.removeEventListener("input", handler);
  window.removeEventListener("change", handler);
  window.removeEventListener("click", handler);
}

/**
  @name useUpdateTemp
  @description This function will check if the target is a setting input-like field.
  In case it is, it will get the id and value for each field case, this will allow to update the template settings.
  @example 
  template = [
  {
    name: "test",
    settings: {
      test: {
        required: true,
        value: "",
        pattern: "^[a-zA-Z0-9]*$",
      },
    },
  },
];
  @param e - Event object, get it by default in the event listener.
  @param template - Template with plugins list and detail settings
*/
function useUpdateTemp(e, template) {
  // Wait some ms that previous update logic is done like datepicker
  setTimeout(() => {
    let inpId, inpValue;

    // Case target is input (a little different for datepicker)
    if (e.target.tagName === "INPUT") {
      inpId = e.target.id;
      inpValue = e.target.hasAttribute("data-timestamp")
        ? e.target.getAttribute("data-timestamp")
        : e.target.value;
    }

    // Case target is select
    if (
      e.target.closest("[data-field-container]") &&
      e.target.hasAttribute("data-setting-id") &&
      e.target.hasAttribute("data-setting-value")
    ) {
      inpId = e.target.getAttribute("data-setting-id");
      inpValue = e.target.getAttribute("data-setting-value");
    }

    // Case target is not an input-like
    if (!inpId) return;

    // update settings
    useUpdateTempSettings(template, inpId, inpValue, e.target);
    useUpdateTempMultiples(template, inpId, inpValue, e.target);
    return template;
  }, 50);
}

/**
  @name useUpdateTempSettings
  @description This function will loop on template settings in order to update the setting value.
  This will check each plugin.settings (what I call regular) instead of other type of settings like multiples (in plugin.multiples).
  This function needs to be call in useUpdateTemp.
  @param template - Template with plugins list and detail settings
  @param inpId - Input id to update
  @param inpValue - Input value to update
*/
function useUpdateTempSettings(template, inpId, inpValue, target) {
  // Case get data-group attribut, this is not a regular setting
  if (target.closest("[data-group]")) return;

  // Try to update settings
  let isSettingUpdated = false;
  for (let i = 0; i < template.length; i++) {
    const plugin = template[i];
    const settings = plugin?.settings;
    if (!settings) continue;
    for (const [key, value] of Object.entries(settings)) {
      if (value.id === inpId) {
        value.value = inpValue;
        isSettingUpdated = true;
        break;
      }
    }
    if (isSettingUpdated) break;
  }
}

/**
  @name useUpdateTempMultiples
  @description This function will loop on template multiples in order to update the setting value.
  This will check each plugin.multiples that can be found in the template.
  This function needs to be call in useUpdateTemp.
  @param template - Template with plugins list and detail settings
  @param inpId - Input id to update
  @param inpValue - Input value to update
*/
function useUpdateTempMultiples(template, inpId, inpValue, target) {
  // Case get data-group attribut, this is not a regular setting
  if (!target.closest("[data-group='multiple']")) return;
  const multName =
    target.closest("[data-group='multiple']").getAttribute("data-mult-name") ||
    "";
  const groupName =
    target.closest("[data-group='multiple']").getAttribute("data-group-name") ||
    "";

  // Check at the same time the inpId without prefix group he is part of
  // And try to update an existing inpId
  // Case we found the inpId, we update the value
  // Case we didn't find existing inpId, we create a new one
  let isSettingUpdated = false;
  for (let i = 0; i < template.length; i++) {
    const plugin = template[i];
    const multiples = plugin?.multiples;
    // Case no multiples, continue
    if (!multiples || Object.keys(multiples).length <= 0) continue;
    // Check if can find mult name in multiples
    if (!(multName in multiples)) continue;
    // Check if can find group name in multiples
    if (!(groupName in multiples[multName])) continue;
    const settings = multiples[multName][groupName];
    for (const [key, value] of Object.entries(settings)) {
      if (value.id !== inpId) continue;
      value.value = inpValue;
      isSettingUpdated = true;
      break;
    }
    if (isSettingUpdated) break;
  }
}

/**
  @name useDelAdvancedMult
  @description This function will delete a group of multiples in the template.
  The way the backend is working is that to delete a group, we need to send the group name with all default values.
  This function needs to be call from the multiples component parent with the template and the group name to delete.
  We will update the values of the group to default values.
  @param template - Template with plugins list and detail settings
  @param multName - Input id to update
  @param groupName - Input value to update
*/
function useDelAdvancedMult(template, multName, groupName) {
  for (let i = 0; i < template.length; i++) {
    const plugin = template[i];
    const multiples = plugin?.multiples;
    if (!multiples) continue;
    if (!(multName in multiples)) continue;
    if (!(groupName in multiples[multName])) continue;
    delete multiples[multName][groupName];
    return;
  }
}

/**
  @name useAddAdvancedMult
  @description This function will add a group of multiple in the template with default values.
  Each plugin has a key "multiples_schema" with each multiples group and their default values.
  We will retrieve the wanted multiple group and add it on the "multiples" key that contains the multiples that apply to the plugin.
  @param template - Template with plugins list and detail settings
  @param multName - Input id to update
*/
function useAddAdvancedMult(template, multName) {
  // Get the right multiple schema
  let multipleSchema = {};
  let plugin;
  let nextGroupId;
  for (let i = 0; i < template.length; i++) {
    plugin = template[i];
    const multiples = plugin?.multiples;
    if (!multiples) continue;
    if (!(multName in multiples)) continue;
    multipleSchema = plugin?.multiples_schema[multName];
    console.log(multipleSchema);
    // Get the highest id in Object.keys(plugin?.multiples[multName])
    nextGroupId = Math.max(...Object.keys(plugin?.multiples[multName])) + 1;
    if (!multipleSchema) return;
    break;
  }
  // Set the default values as value
  for (const [key, value] of Object.entries(multipleSchema)) {
    value.value = value.default;
  }
  // Add new group as first key of plugin.multiples.multName
  plugin.multiples[multName][nextGroupId] = multipleSchema;
  console.log(plugin.multiples[multName]);
}

export {
  useForm,
  useFilter,
  isItemKeyword,
  isItemSelect,
  useCheckPluginsValidity,
  useUpdateTemp,
  useListenTempFields,
  useUnlistenTempFields,
  useDelAdvancedMult,
  useAddAdvancedMult,
};
