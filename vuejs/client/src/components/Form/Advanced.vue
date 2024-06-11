<script setup>
import { defineProps, reactive, onMounted, computed } from "vue";
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
import { useFilterPluginsAdvanced } from "@utils/form.js";
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
    type: Array,
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
  filtered: computed(() => {
    const filters = [
      {
        type: "keyword",
        value: data.keyword,
        keys: ["id", "label", "name", "description", "help", "value"],
      },
      {
        type: "select",
        value: data.type,
        keys: ["type"],
      },
      {
        type: "select",
        value: data.context,
        keys: ["context"],
      },
    ];
    // deep copy
    const template = JSON.parse(JSON.stringify(props.template));
    const filterData = useFilterPluginsAdvanced(template, filters);
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
  tabId: "1",
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
  type: "submit",
  containerClass: "flex justify-center",
};

onMounted(() => {
  // Get first props.forms template name
  data.currPlugin = getFirstPlugin(props.template);
  data.plugins = getPluginNames(props.template);
});
</script>

<template>
  <Container
    :tag="'form'"
    method="POST"
    :containerClass="`col-span-12 w-full m-1 p-1`"
    :columns="props.columns"
  >
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
        v-show="plugin.name === data.currPlugin"
        class="col-span-12 w-full"
      >
        <Title type="card" :title="plugin.name" />
        <Subtitle type="card" :subtitle="plugin.description" />

        <Container
          style="max-height: 300px; overflow: auto"
          class="grid grid-cols-12 w-full relative"
        >
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
