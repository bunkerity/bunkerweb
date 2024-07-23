import { defineStore } from "pinia";
import { ref } from "vue";

/**
  @name createFormStore
  @description This is a factory function that will create a form store.
  This store contains all the logic to manage the form template and update it.
  By defining the form type, this will update some function to avoid errors.  
  @param storeName - Name of the store, must be unique.
  @param formType - Type of form, can be "advanced", "raw" or "easy".
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
    const updateCount = ref(0);
    /**
    @name setTemplate
    @description Set the template we are going to use to generate the form and update it (like adding multiples).
    @param template - Template with plugins list and detail settings
  */
    function setTemplate(template) {
      if (!_isFormTypeAllowed(["advanced", "easy", "raw"])) return;

      const copyTemplate = JSON.parse(JSON.stringify(template));
      template.value = copyTemplate;
      templateBase.value = template;
      templateUI.value = template;
      templateUIFormat.value = template;

      // console.log("template", type.value, template);
      // console.log(typeof template);
      // const formattedData = {};
      // // Loop dict items
      // for (const [key, value] of Object.entries(template)) {
      //   //  Case key "value" is here, we are directly on the right level (and maybe on the raw mode)
      //   if (value?.value) {
      //   }
      //   console.log(key, value);
      //   formattedData[key] = value;
      //   if (!value?.settings || value?.multiples) continue;
      // }
    }

    /**
    @name delMultiple
    @description This function will delete a group of multiples in the template.
    The way the backend is working is that to delete a group, we need to send the group name with all default values.
    This function needs to be call from the multiples component parent with the template and the group name to delete.
    We will update the values of the group to default values.
    @param pluginId - id of the plugin on the template array.
    @param multName - Input id to update
    @param groupName - Input value to update
  */
    function delMultiple(pluginId, multName, groupName) {
      if (!_isFormTypeAllowed(["advanced", "easy"])) return;

      // Get the index of plugin using pluginId
      const index = templateBase.value.findIndex(
        (plugin) => plugin.id === pluginId
      );

      // For back end, we need to keep the group but updating values to default in order to delete it
      for (const [key, value] of Object.entries(
        templateBase.value[index].multiples[multName][groupName]
      )) {
        value.value = value.default;
      }

      // For UI, we can delete the group to avoid rendering it
      delete templateUI.value[index].multiples[multName][groupName];
      updateCount.value++;
    }

    /**
    @name addMultiple
    @description This function will add a group of multiple in the template with default values.
    Each plugin has a key "multiples_schema" with each multiples group and their default values.
    We will retrieve the wanted multiple group and add it on the "multiples" key that contains the multiples that apply to the plugin.
    @param pluginId - id of the plugin on the template array.
    @param multName - multiple group name to add
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
    }

    /**
    @name useListenTempFields
    @description  This will add an handler to all needed event listeners to listen to input, select... fields in order to update the template settings.
    @example 
    function hander(e) {
      // some code before calling _useUpdateTemp
      if (!e.target.closest("[data-advanced-form-plugin]")) return;
      _useUpdateTemp(e, data.base);
    }
  */
    function useListenTempFields() {
      if (!_isFormTypeAllowed(["advanced", "easy"])) return;
      window.addEventListener("input", _useUpdateTemp);
      window.addEventListener("change", _useUpdateTemp);
      window.addEventListener("click", _useUpdateTemp);
    }

    /**
    @name useUnlistenTempFields
    @description  This will stop listening to input, select... fields. Performance optimization and avoid duplicate calls conflicts.
    @example 
    function hander(e) {
      // some code before calling _useUpdateTemp
      if (!e.target.closest("[data-advanced-form-plugin]")) return;
      _useUpdateTemp(e, data.base);
    }
  */
    function useUnlistenTempFields() {
      if (!_isFormTypeAllowed(["advanced", "easy"])) return;
      window.removeEventListener("change", _useUpdateTemp);
      window.removeEventListener("click", _useUpdateTemp);
    }

    /**
    @name _useUpdateTemp
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
      }, 50);
    }

    /**
    @name _useUpdateTempSettings
    @description This function will loop on template settings in order to update the setting value.
    This will check each plugin.settings (what I call regular) instead of other type of settings like multiples (in plugin.multiples).
    This function needs to be call in _useUpdateTemp.
    @param templates - Templates array with plugins list and detail settings
    @param inpId - Input id to update
    @param inpValue - Input value to update
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
    @name _useUpdateTempMultiples
    @description This function will loop on template multiples in order to update the setting value.
    This will check each plugin.multiples that can be found in the template.
    This function needs to be call in _useUpdateTemp.
    @param templates - Templates array with plugins list and detail settings
    @param inpId - Input id to update
    @param inpValue - Input value to update
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
    @name submitForm
    @description This function will format the template base on the form type in order to render a form to submit.
    The send data will change depending on the form type.
    Case raw mode, we will send the raw data as it is.
    Case easy / advanced mode, we will filter value to send only the needed one (enabled and not default).
    After formatting, we will use the utils useSubmitForm from @utils/form to submit the form.
  */
    function submitForm() {
      if (!_isFormTypeAllowed(["advanced", "easy", "raw"])) return;
      console.log("submitForm");
      const formattedData = {};
    }

    /**
    @name $reset
    @description Will reset the template to the original one using the default template. The default template need to be set once.
  */
    function $reset() {
      if (!_isFormTypeAllowed(["advanced", "easy", "raw"])) return;

      templateBase.value = template.value;
      templateUI.value = template.value;
      updateCount.value++;
    }

    /**
    @name _isFormTypeAllowed
    @description Set in on the top of other functions, this will get the function name that called it and check if the form type is allowed to execute this function.
    Case a function is not register, we will not allow it.
  */
    function _isFormTypeAllowed(allowTypes) {
      if (!allowTypes.includes(type.value)) return false;
      return true;
    }

    return {
      templateBase,
      templateUI,
      templateUIFormat,
      setTemplate,
      addMultiple,
      delMultiple,
      useListenTempFields,
      useUnlistenTempFields,
      submitForm,
      $reset,
    };
  });
};

export const useAdvancedForm = createFormStore("advanced", "advanced");
export const useEasyForm = createFormStore("easy", "easy");
export const useRawForm = createFormStore("raw", "raw");
