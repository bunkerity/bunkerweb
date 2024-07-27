/**
  @name utils/form.js
  @description This file contains form utils that will be used in the application by default.
    This file contains functions related to form validation, form submission, and other form utils.
*/

/**
  @name useForm
  @description  This function is a composable wrapper that contains all the form utils functions.
 This function will for example look for JSON-type in the data-submit-form attribute of an element and submit the form with the data object.
  @returns {void}
*/
function useForm() {
  window.addEventListener("click", (e) => {
    if (!e.target.hasAttribute("data-submit-form")) return;
    try {
      const data = JSON.parse(e.target.getAttribute("data-submit-form"));
      useSubmitForm(data);
    } catch (e) {
      console.error(e);
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
  @returns {void}
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
  @returns {array} - Array with error flags and error details
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

export { useForm, useSubmitForm, useCheckPluginsValidity };
