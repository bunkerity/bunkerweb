import { v4 as uuidv4 } from "uuid";

/**
 *  @name utils/global.js
 *  @description This file contains global utils that will be used in the application by default.
 *  This file contains functions related to accessibilities, cookies, and other global utils.
 */

/**
 *  @name useGlobal
 *  @description This function needs to be apply on global level and will do some logic related to form, attributes, and other global actions.
 *  For example, it will check if the target element has a data-link attribute and redirect the user to the define link.
 *  It will check if the target element has a data-submit-form attribute and try to parse it to submit the form.
 *  @returns {void}
 */
function useGlobal() {
  window.addEventListener("click", useDataLinkAttr);
  window.addEventListener("click", useSubmitAttr);
}

/**
 *  @name useSubmitAttr
 *  @description  This function needs to be attach to an event like a click event.
 *  This will check if the target element contains a data-submit-form attribute and try to parse it to submit the form.
 *  @returns {void}
 */
function useSubmitAttr(e) {
  if (!e.target.hasAttribute("data-submit-form")) return;
  try {
    const data = JSON.parse(e.target.getAttribute("data-submit-form"));
    useSubmitForm(data);
  } catch (e) {
    console.error(e);
  }
}

/**
 *  @name useSubmitForm
 *  @description   Create programmatically a form element and submit it with the given data object of type {key: value}.
 *  This will create a FormData and append data arguments to it, retrieve the csrf token and send it with a regular form.
 *  @example
 *  {
 *    instance: "1",
 *    operation: "delete",
 *  }
 *  @param {object} data - Object with the form data to submit.
 *  @returns {void}
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
 *  @name useCheckPluginsValidity
 *  @description  This is a wrapper that will call the correct function to check if plugin settings are valid based on the template and mode.
 *  @example
 *    const template = [
 *      {
 *        name: "test",
 *        settings: {
 *          test: {
 *            required: true,
 *            value: "",
 *            pattern: "^[a-zA-Z0-9]*$",
 *          },
 *        },
 *      },
 *    ];
 *  @param template - Template with plugins list and detail settings
 *  @param {string} mode - Mode to check, can be "advanced", "easy"...
 *  @returns {array} - Array with error flags and error details
 */
function useCheckPluginsValidity(template, mode) {
  let isRegErr = false;
  let isReqErr = false;
  let settingErr = "";
  let pluginErr = "";
  let settingNameErr = "";
  let id = 0;

  if (mode === "advanced") return useCheckAdvancedValidity(template);
  if (mode === "easy") return useCheckEasyValidity(template);
}

/**
 *  @name useCheckAdvancedValidity
 *  @description  Check if plugin settings are valid based on the advanced mode.
 *  @param template - Template with plugins list and detail settings
 *  @returns {array} - Array with error flags and error details
 */
function useCheckAdvancedValidity(template) {
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
 *  @name useCheckEasyValidity
 *  @description  Check if plugin settings are valid based on the easy mode.
 *  @param template - Template with plugins list and detail settings
 *  @returns {array} - Array with error flags and error details
 */
function useCheckEasyValidity(template) {
  let isRegErr = false;
  let isReqErr = false;
  let settingErr = "";
  let pluginErr = "";
  let settingNameErr = "";
  let id = 0;

  for (let i = 0; i < template.length; i++) {
    const step = template[i];
    id = i;
    if (!("plugins" in step)) continue;
    const plugins = step.plugins;
    if (plugins.length <= 0) continue;

    for (let j = 0; j < plugins.length; j++) {
      const plugin = plugins[j];
      const settings = plugin?.settings;
      if (!settings) continue;
      for (const [key, value] of Object.entries(settings)) {
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
    }
  }

  return [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr, id];
}

/**
 *  @name useUUID
 *  @description This function return a unique identifier using uuidv4 and a random number.
 *  Adding random number to avoid duplicate uuids when some components are rendered at the same time.
 *  We can pass a possible existing id, the function will only generate one if the id is empty.
 *  @param {string} [id=""] - Possible existing id, check if it's empty to generate a new one.
 *  @returns {string} - The unique identifier.
 */
function useUUID(id = "") {
  if (id) return id;
  // Generate a random number between 0 and 10000 to avoid duplicate uuids when some components are rendered at the same time
  const random = Math.floor(Math.random() * 10000);

  return uuidv4() + random;
}

/**
 *  @name useEqualStr
 *  @description Get the type of a widget and format it to lowercase if possible. Else return an empty string.
 *  @param {any} type - Try to convert the type to a string in lowercase to compare it with wanted value.
 *  @param {string} compare - The value to compare with, in general the component name.
 *  @returns {boolean} - True if matching, false if not.
 */
function useEqualStr(type, compare) {
  // Check if valid string or can be converted to string
  try {
    return String(type).toLowerCase() === compare.toLowerCase() ? true : false;
  } catch (e) {
    console.error(e);
    return false;
  }
}

/**
 *  @name useDataLinkAttr
 *  @description Check from event if the target has a data-link attribute. Case it is, it will be used to redirect the user to the define link.
 * This is useful to avoid using the <a> tag and use a <div> or <button> instead.
 *  @param {event} e - The event to attach the function logic
 *  @returns {void}
 */
function useDataLinkAttr(e) {
  if (!e.target.hasAttribute("data-link")) return;
  const link = e.target.getAttribute("data-link");
  window.location.href = link;
}

export {
  useGlobal,
  useUUID,
  useEqualStr,
  useSubmitForm,
  useCheckPluginsValidity,
};
