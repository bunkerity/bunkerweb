import { v4 as uuidv4 } from "uuid";
import { useDisplayStore } from "@store/global.js";

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
 *  @returns {Void}
 */
function useGlobal() {
  window.addEventListener("click", useDataLinkAttr);
  window.addEventListener("click", useSubmitAttr);
  window.addEventListener("click", useHandleDisplay);
}

/**
 *  @name useSubmitAttr
 *  @description  This function needs to be attach to an event like a click event.
 *  This will check if the target element contains a data-submit-form attribute and try to parse it to submit the form.
 *  @returns {Void}
 */
function useSubmitAttr(e) {
  if (!e.target.hasAttribute("data-submit-form")) return;
  try {
    const data = JSON.parse(e.target.getAttribute("data-submit-form"));
    const endpoint = e.target.hasAttribute("data-submit-endpoint")
      ? `${window.location.origin}${
          window.location.pathname
        }${e.target.getAttribute("data-submit-endpoint")}`
      : "";
    const method = e.target.hasAttribute("data-submit-endpoint")
      ? e.target.getAttribute("data-submit-method")
      : "POST";
    useSubmitForm(data, endpoint, method);
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
 *  @param {Object} data - Object with the form data to submit.
 *  @param {String} [submitEndpoint=""] - The endpoint to submit the form.
 *  @param {String} [method="POST"] - The http method
 *  @returns {Void}
 */
function useSubmitForm(data, submitEndpoint = "", method = "POST") {
  // Create a form element
  const form = document.createElement("form");
  form.style.display = "none";
  form.method = method;
  form.action = submitEndpoint;
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
 *  @description  This is a wrapper that will check the validity of the plugins settings based on the defined mode.
 *  @param {Object|Array} template - Template with plugins list and detail settings
 *  @param {String} mode - Mode to check, can be "advanced", "easy"...
 *  @returns {array} - Array with error flags and error details
 */
function useCheckPluginsValidity(template, mode) {
  // Case advanced, the template is a list of plugins so we can check and return directly
  if (mode === "advanced") {
    return _checkSettingsValidityFromPlugins(template, mode);
  }

  // Case easy mode, there is a list of plugins in each step so we need to iterate over the steps
  if (mode === "easy") {
    let data = [];
    for (let stepId = 0; stepId < template.length; stepId++) {
      const step = template[stepId];

      if (!("plugins" in step)) continue;

      // Check regular settings
      const plugins = step?.plugins;
      data = _checkSettingsValidityFromPlugins(plugins, stepId);
      // data[0] is isRegErr, data[1] is isReqErr
      if (data[0] || data[1]) return data;
    }
    return data;
  }
}

/**
 *  @name _checkSettingsValidityFromPlugins
 *  @description  Check settings from a list of plugins and return the error flags and error details.
 *  @param {Object|Array} template - The template to check
 *  @param {String|Number} [id=0] - The id of the plugin or the current step.
 *  @returns {array} - Return [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr, id]
 */
function _checkSettingsValidityFromPlugins(plugins, id = 0) {
  let isRegErr = false;
  let isReqErr = false;
  let settingErr = "";
  let pluginErr = "";
  let settingNameErr = "";

  [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr] =
    _checkRegularSettingsValidityFromPlugins(plugins);
  if (isRegErr || isReqErr)
    return [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr, id];

  // CHeck multiples settings
  [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr] =
    _checkMultipleSettingsValidityFromPlugins(plugins);
  if (isRegErr || isReqErr)
    return [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr, id];

  return [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr, id];
}

/**
 *  @name _checkRegularSettingsValidityFromPlugins
 *  @description  Access regular settings from a plugin and return the error flags and error details.
 *  @param {Object|Array} template - The template to check
 *  @returns {array} - Return empty array or [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr]
 */
function _checkRegularSettingsValidityFromPlugins(plugins) {
  let result;
  for (let j = 0; j < plugins.length; j++) {
    const plugin = plugins[j];
    if (!("settings" in plugin)) continue;
    const settings = plugin?.settings;
    for (const [key, value] of Object.entries(settings)) {
      result = _isSettingValid(key, value, plugin.name);
      if (result.stop) return result.data;
    }
  }
  // fallback
  return result?.data ? result.data : [];
}

/**
 *  @name _checkMultipleSettingsValidityFromPlugins
 *  @description  Access multiple settings from a plugin and return the error flags and error details.
 *  @param {Object|Array} template - The template to check
 *  @returns {array} - Return empty array or [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr]
 */
function _checkMultipleSettingsValidityFromPlugins(plugins) {
  let result;
  for (let j = 0; j < plugins.length; j++) {
    const plugin = plugins[j];
    if (!("multiples" in plugin)) continue;
    for (const [multName, multGroups] of Object.entries(plugin.multiples)) {
      for (const [multGroup, multSettings] of Object.entries(multGroups)) {
        for (const [key, value] of Object.entries(multSettings)) {
          result = _isSettingValid(key, value, plugin.name);
          if (result.stop) return result.data;
        }
      }
    }
  }
  // fallback
  return result?.data ? result.data : [];
}

/**
 *  @name _isSettingValid
 *  @description  Check if a setting is valid based on the pattern and required flags.
 *  @param {String} key - The name of the setting
 *  @param {Object} value - Setting value used to check if it's valid
 *  @param {String} pluginName - The name of the plugin
 *  @returns {Object} - Return object with {stop, data : [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr]}
 */
function _isSettingValid(key, value, pluginName) {
  let is_reg_valid = true;
  let is_req_valid = true;

  if (value.required && !value.value) is_req_valid = false;

  if (value.pattern && value.value) {
    const regex = new RegExp(value.pattern);
    if (!regex.test(value.value)) is_reg_valid = false;
  }

  const isRegErr = is_reg_valid ? false : true;
  const isReqErr = is_req_valid ? false : true;
  const settingErr = isRegErr || isRegErr ? key : "";
  const settingNameErr = isRegErr || isRegErr ? value.name : "";
  const pluginErr = isRegErr || isRegErr ? pluginName : "";

  return {
    stop: isRegErr || isReqErr ? true : false,
    data: [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr],
  };
}

/**
 *  @name useUUID
 *  @description This function return a unique identifier using uuidv4 and a random number.
 *  Adding random number to avoid duplicate uuids when some components are rendered at the same time.
 *  We can pass a possible existing id, the function will only generate one if the id is empty.
 *  @param {String} [id=""] - Possible existing id, check if it's empty to generate a new one.
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
 *  @param {Any} type - Try to convert the type to a string in lowercase to compare it with wanted value.
 *  @param {String} compare - The value to compare with, in general the component name.
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
 *  @param {Event} e - The event to attach the function logic
 *  @returns {Void}
 */
function useDataLinkAttr(e) {
  if (!e.target.hasAttribute("data-link")) return;
  const link = e.target.getAttribute("data-link");
  window.location.href = link;
}

/**
 *  @name useHandleDisplay
 *  @description Listen to click event and check if the clicked element has a data-display-index attribute.
 *  Case it has, we will update the display store with the data-display-index value.
 *  @param {Event} e - The event to attach the function logic
 *  @returns {Void}
 */
function useHandleDisplay(e) {
  const displayStore = useDisplayStore();
  if (
    !e.target.hasAttribute("data-display-index") ||
    !e.target.hasAttribute("data-display-group")
  )
    return;
  try {
    const index = e.target.getAttribute("data-display-index");
    const group = e.target.getAttribute("data-display-group");
    displayStore.setDisplay(group, index);
  } catch (e) {
    console.error(e);
    console.error("Display index bad format");
  }
}

export {
  useGlobal,
  useUUID,
  useEqualStr,
  useSubmitForm,
  useCheckPluginsValidity,
};
