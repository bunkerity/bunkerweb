import { defineStore } from "pinia";
import { ref } from "vue";
import { useSubmitForm } from "@utils/global.js";

/**
 *  @name createFormStore
 *  @description This is a factory function that will create a form store.
 *  This store contains all the logic to manage the form template and update it.
 *  By defining the form type, this will update some function to avoid errors.
 *  @param {string} storeName - Name of the store, must be unique.
 *  @param {string} formType - Type of form, can be "advanced", "raw" or "easy".
 *  @returns {store} - Return a form store with all the logic to manage the form template and update it.
 */
export const createFormStore = (storeName, formType) => {
  return defineStore(storeName, () => {
    // Define the type of form we are going to use.
    // This will change some logic.
    const type = ref(formType);
    // Default template, don't touch it. It will be used to reset the template.
    const template = ref({});
    // Base template will keep every data (data that doesn't need to be render on UI but need to be there for backend).
    const templateBase = ref({});
    // UI template will keep the data that will be render on UI.
    const templateUI = ref({});
    // UI template will keep the data that will be render on UI with additionnal format like filtering.
    const templateUIFormat = ref({});
    // Store any raw information that can be usefull for the form.
    const rawData = ref("");
    // Increment when some functions are updating template to force rerendering when attach to a component using the reactive value.
    const updateCount = ref(0);
    // After a submit attempt or an event listener updating a template, check if a date is updating (different from default and previous value).
    const isUpdateData = ref(false);
    // Data we gonna submit
    const formattedData = ref({});
    // Get additionnal data for submit
    const operation = ref("");
    const oldServerName = ref("");

    /**
     *  @name setOperation
     *  @description Set the operation when we will submit the form.
     *  @param {string} operation - Operation to set
     *  @returns {void}
     */
    function setOperation(value) {
      operation.value = value;
    }

    /**
     *  @name setOldServerName
     *  @description Set the operation when we will submit the form.
     *  @param {string} oldServeName - old server name to set
     *  @returns {void}
     */
    function setOldServerName(value) {
      oldServerName.value = value;
    }

    /**
     *  @name setTemplate
     *  @description Set the template we are going to use to generate the form and update it (like adding multiples).
     *  @param {object} tempData - Template with plugins list and detail settings
     *  @param {boolean} [force=false] - Force to update the template even if already set before
     *  @returns {void}
     */
    function setTemplate(tempData, force = false) {
      if (!_isFormTypeAllowed(["advanced", "easy", "raw"])) return;
      if (Object.keys(template.value).length > 0 && !force) return;
      // Unlink the template
      template.value = JSON.parse(JSON.stringify(tempData));
      templateBase.value = JSON.parse(JSON.stringify(tempData));
      templateUI.value = JSON.parse(JSON.stringify(tempData));
      templateUIFormat.value = templateUI.value;
      _updateTempState();
      console.log("format", formattedData.value);
    }

    /**
     *  @name setRawData
     *  @description Set raw data that can be usefull for the form.
     *  @param {array} data - Template with plugins list and detail settings
     *  @param {boolean} [force=false] - Template with plugins list and detail settings
     *  @returns {void}
     */
    function setRawData(data, force = false) {
      if (!_isFormTypeAllowed(["advanced", "easy", "raw"])) return;
      if (rawData.value && !force) return;
      rawData.value = data;
    }

    /**
     *  @name delMultiple
     *  @description This function will delete a group of multiples in the template.
     *  The way the backend is working is that to delete a group, we need to send the group name with all default values.
     *  This function needs to be call from the multiples component parent with the template and the group name to delete.
     *  We will update the values of the group to default values.
     *  @param {string} pluginId - id of the plugin on the template array.
     *  @param {string} multName - Input id to update
     *  @param {string|number} groupName - Input value to update
     *  @returns {void}
     */
    function delMultiple(pluginId, multName, groupName) {
      if (!_isFormTypeAllowed(["advanced", "easy"])) return;

      // Get the index of plugin using pluginId
      const index = templateBase.value.findIndex(
        (plugin) => plugin.id === pluginId
      );

      // For back end, we need to keep the group but updating values to default in order to delete it
      for (const [settName, setting] of Object.entries(
        templateBase.value[index].multiples[multName][groupName]
      )) {
        setting.value = setting.default;
      }

      // For UI, we can delete the group to avoid rendering it
      delete templateUI.value[index].multiples[multName][groupName];
      _updateTempState();
    }

    /**
     *  @name addMultiple
     *  @description This function will add a group of multiple in the template with default values.
     *  Each plugin has a key "multiples_schema" with each multiples group and their default values.
     *  We will retrieve the wanted multiple group and add it on the "multiples" key that contains the multiples that apply to the plugin.
     *  @param {string} pluginId - id of the plugin on the template array.
     *  @param {string} multName - multiple group name to add
     *  @returns {void}
     */
    function addMultiple(pluginId, multName) {
      if (!_isFormTypeAllowed(["advanced", "easy"])) return;

      // Get the index of plugin using pluginId
      const index = templateBase.value.findIndex(
        (plugin) => plugin.id === pluginId
      );
      // Get the right multiple schema
      const multipleSchema = JSON.parse(
        JSON.stringify(templateBase.value[index]?.multiples_schema[multName])
      );
      const newMultiple = {};

      // Get the highest id in Object.keys(plugin?.multiples[multName])
      const nextGroupId =
        Math.max(
          ...Object.keys(templateBase.value[index]?.multiples[multName])
        ) + 1;

      // Set the default values as value
      for (const [key, value] of Object.entries(multipleSchema)) {
        value.value = value.default;
        newMultiple[`${key}${nextGroupId > 0 ? "_" + nextGroupId : ""}`] =
          value;
      }
      // Add new group as first key of plugin.multiples.multName
      templateBase.value[index].multiples[multName][nextGroupId] = newMultiple;
      // We need to show the new group on UI too
      templateUI.value[index].multiples[multName][nextGroupId] = newMultiple;
      updateCount.value++;
      _updateTempState();
    }

    /**
     *  @name useListenTempFields
     *  @description  This will add an handler to all needed event listeners to listen to input, select... fields in order to update the template settings.
     *  @example
     *  function hander(e) {
     *    // some code before calling _useUpdateTemp
     *    if (!e.target.closest("[data-advanced-form-plugin]")) return;
     *    _useUpdateTemp(e, data.base);
     *  }
     *  @returns {void}
     */
    function useListenTempFields() {
      if (!_isFormTypeAllowed(["advanced", "easy"])) return;
      window.addEventListener("input", _useUpdateTemp);
      window.addEventListener("change", _useUpdateTemp);
      window.addEventListener("click", _useUpdateTemp);
    }

    /**
     *  @name useUnlistenTempFields
     *  @description  This will stop listening to input, select... fields. Performance optimization and avoid duplicate calls conflicts.
     *  @example
     *  function hander(e) {
     *    // some code before calling _useUpdateTemp
     *    if (!e.target.closest("[data-advanced-form-plugin]")) return;
     *    _useUpdateTemp(e, data.base);
     *  }
     *  @returns {void}
     */
    function useUnlistenTempFields() {
      if (!_isFormTypeAllowed(["advanced", "easy"])) return;
      window.removeEventListener("change", _useUpdateTemp);
      window.removeEventListener("click", _useUpdateTemp);
    }

    /**
  *  @name _useUpdateTemp
  *  @description This function will check if the target is a setting input-like field.
  *  In case it is, it will get the id and value for each field case, this will allow to update the template settings.
  *  @example 
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
  *  @param e - Event object, get it by default in the event listener.
  *  @returns {void}
  */
    function _useUpdateTemp(e) {
      if (!_isFormTypeAllowed(["advanced", "easy"])) return;

      const templates = [templateBase.value, templateUI.value];
      // Filter to avoid multiple calls
      if (!e.target.closest("[data-advanced-form-plugin]")) return;
      if (e.type === "change" && e.target.tagName === "INPUT") return;
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
        _useUpdateTempSettings(templates, inpId, inpValue, e.target);
        _useUpdateTempMultiples(templates, inpId, inpValue, e.target);
        _updateTempState();
      }, 50);
    }

    /**
     *  @name _useUpdateTempSettings
     *  @description This function will loop on template settings in order to update the setting value.
     *  This will check each plugin.settings (what I call regular) instead of other type of settings like multiples (in plugin.multiples).
     *  This function needs to be call in _useUpdateTemp.
     *  @param {array} templates - Templates array with plugins list and detail settings
     *  @param {string|number} inpId - Input id to update
     *  @param {string|number} inpValue - Input value to update
     *  @returns {void}
     */
    function _useUpdateTempSettings(templates, inpId, inpValue, target) {
      if (!_isFormTypeAllowed(["advanced", "easy"])) return;

      // Case get data-group attribut, this is not a regular setting
      if (target.closest("[data-group]")) return;

      for (let i = 0; i < templates.length; i++) {
        const template = templates[i];

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
    }

    /**
     *  @name _useUpdateTempMultiples
     *  @description This function will loop on template multiples in order to update the setting value.
     *  This will check each plugin.multiples that can be found in the template.
     *  This function needs to be call in _useUpdateTemp.
     *  @param {array} templates - Templates array with plugins list and detail settings
     *  @param {string|number} inpId - Input id to update
     *  @param {string|number} inpValue - Input value to update
     *  @returns {void}
     */
    function _useUpdateTempMultiples(templates, inpId, inpValue, target) {
      if (!_isFormTypeAllowed(["advanced", "easy"])) return;
      // Case get data-group attribut, this is not a regular setting
      if (!target.closest("[data-group='multiple']")) return;
      const multName =
        target
          .closest("[data-group='multiple']")
          .getAttribute("data-mult-name") || "";
      const groupName =
        target
          .closest("[data-group='multiple']")
          .getAttribute("data-group-name") || "";

      for (let i = 0; i < templates.length; i++) {
        const template = templates[i];
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
    }

    /**
     *  @name submit
     *  @description Case we have at least one setting updating, we will allow to submit the form.
     *  @returns {void}
     */
    function submit() {
      if (!_isFormTypeAllowed(["advanced", "easy", "raw"])) return;
      _updateTempState();
      if (!isUpdateData.value) return;

      data = JSON.parse(JSON.stringify(formattedData.value));
      data["operation"] = operation.value;
      data["OLD_SERVER_NAME"] = oldServerName.value;
      print(data);
    }

    /**
     *  @name _updateTempState
     *  @description This function will run after a template update and will do two things :
     *  1. Format the template to send needed data to the backend.
     *  2. Check if at least one setting is updating. Case true, we will allow to submit the form.
     *  @returns {void}
     */
    function _updateTempState() {
      formattedData.value = {};

      // Loop dict items
      for (const [key, value] of Object.entries(templateBase.value)) {
        //  Case we have a primitive value as value, we can stop here
        if (typeof value !== "object") {
          formattedData.value = templateBase.value;
          break;
        }

        // Case no wanted keys, continue
        if (!value?.settings && !value?.multiples) continue;

        _getPluginSettingsValue(value, formattedData.value);
        _getPluginMultiplesValue(value, formattedData.value);
      }
      isUpdateData.value =
        Object.keys(formattedData.value).length > 0 ? true : false;
    }

    /**
     *  @name _getPluginMultiplesValue
     *  @description Case we have a multiples key, we have a plugin object.
     *  We will loop on each multiples settings and check if the value is different from the previous value in order to add it to the formattedData.
     *  @returns {void}
     */
    function _getPluginMultiplesValue(value) {
      // Get multiples value
      if (!value?.multiples) return;
      for (const [multName, multGroups] of Object.entries(value.multiples)) {
        for (const [groupName, group] of Object.entries(multGroups)) {
          for (const [settName, setting] of Object.entries(group)) {
            _checkSettingToAddValue(setting, settName);
          }
        }
      }
    }

    /**
     *  @name _getPluginSettingsValue
     *  @description Case we have a settings key, we have a plugin object.
     *  We will loop on each settings and check if the value is different from the previous value in order to add it to the formattedData.
     *  @returns {void}
     */
    function _getPluginSettingsValue(value) {
      if (!value?.settings) return;

      for (const [settName, setting] of Object.entries(value.settings)) {
        _checkSettingToAddValue(setting, settName);
      }
    }

    /**
     *  @name _checkSettingToAddValue
     *  @description Check if the setting value is different from the previous value in order to add it to the formattedData.
     *  @returns {void}
     */
    function _checkSettingToAddValue(setting, settingName) {
      // Case current value is the same as previous, we don't need to send it
      if (setting?.value === setting?.prev_value) return;
      formattedData.value[settingName] = setting?.value;
    }

    /**
     *  @name _isFormTypeAllowed
     *  @description Set in on the top of other functions, this will get the function name that called it and check if the form type is allowed to execute this function.
     *  Case a function is not register, we will not allow it.
     *  @returns {boolean} - Return true if the form type is allowed to execute the function.
     */
    function _isFormTypeAllowed(allowTypes) {
      if (!allowTypes.includes(type.value)) return false;
      return true;
    }

    /**
     *  @name $reset
     *  @description Will reset the template to the original one using the default template. The default template need to be set once.
     *  @returns {void}
     */
    function $reset() {
      if (!_isFormTypeAllowed(["advanced", "easy", "raw"])) return;

      templateBase.value = template.value;
      templateUI.value = template.value;
      updateCount.value++;
    }

    return {
      templateBase,
      templateUI,
      templateUIFormat,
      rawData,
      isUpdateData,
      setTemplate,
      setRawData,
      setOldServerName,
      setOperation,
      addMultiple,
      delMultiple,
      useListenTempFields,
      useUnlistenTempFields,
      submit,
      $reset,
    };
  });
};

export const useAdvancedForm = createFormStore("advanced", "advanced");
export const useEasyForm = createFormStore("easy", "easy");
export const useRawForm = createFormStore("raw", "raw");
