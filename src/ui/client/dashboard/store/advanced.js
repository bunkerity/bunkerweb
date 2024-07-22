import { defineStore } from "pinia";
import { ref } from "vue";

/**
  @name useAdvancedForm
  @description Store to share the template and others form data.
*/
export const useAdvancedForm = defineStore("advanced", () => {
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
    template.value = template;
    templateBase.value = template;
    templateUI.value = JSON.parse(JSON.stringify(template));
    templateUIFormat.value = JSON.parse(JSON.stringify(template));
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
      Math.max(...Object.keys(templateBase.value[index]?.multiples[multName])) +
      1;

    // Set the default values as value
    for (const [key, value] of Object.entries(multipleSchema)) {
      value.value = value.default;
      newMultiple[`${key}${nextGroupId > 0 ? "_" + nextGroupId : ""}`] = value;
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
    // some code before calling useUpdateTemp
    if (!e.target.closest("[data-advanced-form-plugin]")) return;
    useUpdateTemp(e, data.base);
  }
*/
  function useListenTempFields() {
    window.addEventListener("input", useUpdateTemp);
    window.addEventListener("change", useUpdateTemp);
    window.addEventListener("click", useUpdateTemp);
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
*/
  function useUnlistenTempFields() {
    window.removeEventListener("change", useUpdateTemp);
    window.removeEventListener("click", useUpdateTemp);
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
  @param templates - Array of templates to update
*/
  function useUpdateTemp(e, templates) {
    templates = [templateBase.value, templateUI.value];
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
      useUpdateTempSettings(templates, inpId, inpValue, e.target);
      useUpdateTempMultiples(templates, inpId, inpValue, e.target);
    }, 50);
  }

  /**
  @name useUpdateTempSettings
  @description This function will loop on template settings in order to update the setting value.
  This will check each plugin.settings (what I call regular) instead of other type of settings like multiples (in plugin.multiples).
  This function needs to be call in useUpdateTemp.
  @param templates - Templates array with plugins list and detail settings
  @param inpId - Input id to update
  @param inpValue - Input value to update
*/
  function useUpdateTempSettings(templates, inpId, inpValue, target) {
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
  @name useUpdateTempMultiples
  @description This function will loop on template multiples in order to update the setting value.
  This will check each plugin.multiples that can be found in the template.
  This function needs to be call in useUpdateTemp.
  @param templates - Templates array with plugins list and detail settings
  @param inpId - Input id to update
  @param inpValue - Input value to update
*/
  function useUpdateTempMultiples(templates, inpId, inpValue, target) {
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
  @name $reset
  @description Will reset the template to the original one using the default template. The default template need to be set once.
*/
  function $reset() {
    templateBase.value = template.value;
    templateUI.value = template.value;
    updateCount.value++;
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
    $reset,
  };
});
