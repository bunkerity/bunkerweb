<script setup>
import { defineProps, reactive, onMounted, computed, onUnmounted } from "vue";
import Container from "@components/Widget/Container.vue";
import Fields from "@components/Form/Fields.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
import Input from "@components/Forms/Field/Input.vue";
import Select from "@components/Forms/Field/Select.vue";
import Button from "@components/Widget/Button.vue";
import { v4 as uuidv4 } from "uuid";
import { plugin_types } from "@utils/variables";
import { useFilter } from "@utils/form.js";
/**
  @name Form/Advanced.vue
  @description This component is used to create a complete advanced form with plugin selection.
  @example
  template: [
        {
          columns: { pc: 6, tablet: 12, mobile: 12 },
          id: "test-check",
          value: "yes",
          label: "Checkbox",
          name: "checkbox",
          required: true,
          hideLabel: false,
          headerClass: "text-red-500",
          inpType: "checkbox",
        },
        {
          id: "test-input",
          value: "yes",
          type: "text",
          name: "test-input",
          disabled: false,
          required: true,
          label: "Test input",
          pattern: "(test)",
          inpType: "input",
        },
      ],
  @param {object} template - Template object with plugin and settings data.
  @param {string} containerClass - Container
  @param {object} columns - Columns object.
*/

const props = defineProps({
  // id && value && method
  template: {
    type: Object,
    required: true,
    default: {},
  },

  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  columns: {
    type: Object,
    required: false,
    default: {},
  },
});

const data = reactive({
  currPlugin: "",
  plugins: [],
  keyword: "",
  type: "all",
  context: "all",
  base: JSON.parse(JSON.stringify(props.template)),
  filtered: computed(() => {
    const filterPlugin = [
      {
        type: "select",
        value: data.type,
        keys: ["type"],
      },
    ];

    const filterSettings = [
      {
        type: "keyword",
        value: data.keyword,
        keys: [
          "id",
          "label",
          "name",
          "description",
          "help",
          "value",
          "setting_name",
        ],
      },
      {
        type: "select",
        value: data.context,
        keys: ["context"],
      },
    ];

    // Deep copy
    const template = JSON.parse(JSON.stringify(data.base));
    // Start plugin filtering
    const filterPlugins = useFilter(template, filterPlugin);
    // Filter settings
    filterPlugins.forEach((plugin, id) => {
      // loop on plugin settings dict
      const settings = [];
      for (const [key, value] of Object.entries(plugin.settings)) {
        // add to value the key as setting_name
        settings.push({ ...value, setting_name: key });
      }
      const filterSettingsData = useFilter(settings, filterSettings);
      // Transform list of dict by a dict of dict with setting_name as key and add update plugin settings
      const settingsData = {};
      filterSettingsData.forEach((setting) => {
        settingsData[setting.setting_name] = setting;
      });
      filterPlugins[id].settings = settingsData;
    });

    // Case no settings found, remove plugin
    const filterData = filterPlugins.filter((plugin) => {
      return Object.keys(plugin.settings).length > 0;
    });
    data.plugins = getPluginNames(filterData);
    data.currPlugin = getFirstPlugin(filterData);
    return filterData;
  }),
});

function getFirstPlugin(template) {
  try {
    return template[0]["name"];
  } catch (e) {
    return "";
  }
}

function getPluginNames(template) {
  try {
    const pluginNames = [];
    // Loop on each dict from template list
    for (const plugin of template) {
      // Return the first plugin
      pluginNames.push(plugin.name);
    }
    return pluginNames;
  } catch (e) {
    return [];
  }
}

const comboboxPlugin = {
  id: uuidv4(),
  name: uuidv4(),
  disabled: false,
  required: false,
  label: "dashboard_plugins",
  popovers: [
    {
      text: "inp_combobox_advanced_desc",
      iconName: "info",
      iconColor: "info",
    },
  ],
  columns: { pc: 3, tablet: 4, mobile: 12 },
};

const inpKeyword = {
  id: uuidv4(),
  value: "",
  type: "text",
  name: uuidv4(),
  label: "inp_search_settings",
  placeholder: "inp_keyword",
  popovers: [
    {
      text: "inp_search_settings_desc",
      iconName: "info",
      iconColor: "info",
    },
  ],
  columns: { pc: 3, tablet: 4, mobile: 12 },
};

const selectType = {
  id: uuidv4(),
  value: "all",
  // add 'all' as first value
  values: ["all"].concat(plugin_types),
  name: uuidv4(),
  label: "inp_select_plugin_type",
  popovers: [
    {
      text: "inp_select_plugin_type_desc",
      iconName: "info",
      iconColor: "info",
    },
  ],
  columns: { pc: 3, tablet: 4, mobile: 12 },
};

const selectContext = {
  id: uuidv4(),
  value: "all",
  // add 'all' as first value
  values: ["all", "multisite", "global"],
  name: uuidv4(),
  label: "inp_select_plugin_context",
  popovers: [
    {
      text: "inp_select_plugin_context_desc",
      iconName: "info",
      iconColor: "info",
    },
  ],
  columns: { pc: 3, tablet: 4, mobile: 12 },
};

const buttonSave = {
  id: uuidv4(),
  text: "action_save",
  disabled: false,
  color: "success",
  size: "normal",
  type: "bouton",
  attrs: {
    "data-submit-form": JSON.stringify(data.base),
  },
  containerClass: "flex justify-center",
};

function updateInp(e) {
  // Check if target is child of data-advanced-form
  if (!e.target.closest("[data-advanced-form-plugin]")) return;

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

    data.base.find((plugin) => {
      const settings = plugin["settings"];
      // loop on each settings from plugin
      for (const [key, value] of Object.entries(settings)) {
        if (value.id === inpId) {
          value.value = inpValue;
        }
      }
    });
  }, 50);
}

onMounted(() => {
  // Get first props.forms template name
  data.currPlugin = getFirstPlugin(props.template);
  data.plugins = getPluginNames(props.template);
  // Store update data on
  window.addEventListener("input", updateInp);
  window.addEventListener("change", updateInp);
  window.addEventListener("click", updateInp);
});

onUnmounted(() => {
  window.removeEventListener("input", updateInp);
  window.removeEventListener("change", updateInp);
  window.removeEventListener("click", updateInp);
});
</script>

<template>
  <Container
    data-advanced-form
    :tag="'form'"
    method="POST"
    :containerClass="`col-span-12 w-full m-1 p-1`"
    :columns="props.columns"
  >
    <Title type="card" :title="'dashboard_advanced_mode'" />
    <Subtitle type="card" :subtitle="'dashboard_advanced_mode_subtitle'" />
    <Container :containerClass="`grid grid-cols-12 col-span-12 w-full`">
      <Combobox
        v-bind="comboboxPlugin"
        :value="data.currPlugin"
        :values="data.plugins"
        @inp="data.currPlugin = $event"
      />
      <Input @inp="(v) => (data.keyword = v)" v-bind="inpKeyword" />
      <Select @inp="(v) => (data.type = v)" v-bind="selectType" />
      <Select @inp="(v) => (data.context = v)" v-bind="selectContext" />
    </Container>
    <template v-for="plugin in data.filtered">
      <Container
        data-advanced-form-plugin
        v-if="plugin.name === data.currPlugin"
        class="col-span-12 w-full"
      >
        <Title type="card" :title="plugin.name" />
        <Subtitle type="card" :subtitle="plugin.description" />

        <Container class="grid grid-cols-12 w-full relative">
          <template
            v-for="(setting, name, index) in plugin.settings"
            :key="index"
          >
            <Fields :setting="setting" />
          </template>
        </Container>
      </Container>
    </template>
    <Button v-bind="buttonSave" />
  </Container>
</template>
