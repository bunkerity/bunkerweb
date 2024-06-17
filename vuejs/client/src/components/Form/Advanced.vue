<script setup>
import { defineProps, reactive, onMounted, computed, onUnmounted } from "vue";
import Container from "@components/Widget/Container.vue";
import Fields from "@components/Form/Fields.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
import Button from "@components/Widget/Button.vue";
import Text from "@components/Widget/Text.vue";
import Filter from "@components/Widget/Filter.vue";
import { v4 as uuidv4 } from "uuid";
import { plugin_types } from "@utils/variables";
import {
  useCheckPluginsValidity,
  useUpdateTempSettings,
  useListenTemp,
  useUnlistenTemp,
} from "@utils/form.js";
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
  base: JSON.parse(JSON.stringify(props.template)),
  isRegErr: false,
  isReqErr: false,
  settingErr: "",
  pluginErr: "",
  // Add filtering and check validity with regex and required
  format: JSON.parse(JSON.stringify(props.template)),
});

const filters = [
  {
    filter: "settings",
    filterName: "keyword",
    type: "keyword",
    value: "",
    keys: [
      "id",
      "label",
      "name",
      "description",
      "help",
      "value",
      "setting_name",
    ],
    field: {
      id: uuidv4(),
      value: "",
      type: "text",
      name: uuidv4(),
      containerClass: "setting",
      label: "inp_search_settings",
      placeholder: "inp_keyword",
      isClipboard: false,
      popovers: [
        {
          text: "inp_search_settings_desc",
          iconName: "info",
          iconColor: "info",
        },
      ],
      columns: { pc: 3, tablet: 4, mobile: 12 },
    },
  },
  {
    filter: "default",
    filterName: "type",
    type: "select",
    value: "all",
    keys: ["type"],
    field: {
      id: uuidv4(),
      value: "all",
      // add 'all' as first value
      values: ["all"].concat(plugin_types),
      name: uuidv4(),
      onlyDown: true,
      label: "inp_select_plugin_type",
      containerClass: "setting",
      popovers: [
        {
          text: "inp_select_plugin_type_desc",
          iconName: "info",
          iconColor: "info",
        },
      ],
      columns: { pc: 3, tablet: 4, mobile: 12 },
    },
  },
  {
    filter: "settings",
    filterName: "context",
    type: "select",
    value: "all",
    keys: ["context"],
    field: {
      id: uuidv4(),
      value: "all",
      // add 'all' as first value
      values: ["all", "multisite", "global"],
      name: uuidv4(),
      onlyDown: true,
      containerClass: "setting",
      label: "inp_select_plugin_context",
      popovers: [
        {
          text: "inp_select_plugin_context_desc",
          iconName: "info",
          iconColor: "info",
        },
      ],
      columns: { pc: 3, tablet: 4, mobile: 12 },
    },
  },
];

function filter(filterData) {
  setValidity();
  data.format = filterData;
  data.plugins = getPluginNames(filterData);
  data.currPlugin = getFirstPlugin(filterData);
}

function setValidity() {
  const [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr, id] =
    useCheckPluginsValidity(data.base);
  data.isRegErr = isRegErr;
  data.isReqErr = isReqErr;
  data.settingErr = settingErr;
  data.pluginErr = pluginErr;
}

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

function updateTemplate(e) {
  if (!e.target.closest("[data-advanced-form-plugin]")) return;
  useUpdateTempSettings(e, data.base);
}

const comboboxPlugin = {
  id: uuidv4(),
  name: uuidv4(),
  disabled: false,
  required: false,
  onlyDown: true,
  containerClass: "setting",
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

const buttonSave = {
  id: uuidv4(),
  text: "action_save",
  color: "success",
  size: "normal",
  type: "bouton",
  attrs: {
    "data-submit-form": JSON.stringify(data.base),
  },
  containerClass: "flex justify-center",
};

onMounted(() => {
  // Get first props.forms template name
  data.currPlugin = getFirstPlugin(props.template);
  data.plugins = getPluginNames(props.template);
  setValidity();
  // Store update data on

  // I want updatInp to access event, data.base and the container attribut
  useListenTemp(updateTemplate);
});

onUnmounted(() => {
  useUnlistenTemp(updateTemplate);
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
    <Combobox
      v-bind="comboboxPlugin"
      :value="data.currPlugin"
      :values="data.plugins"
      @inp="data.currPlugin = $event"
    />
    <Filter
      v-if="filters.length"
      @filter="(v) => filter(v)"
      :data="data.base"
      :filters="filters"
    />
    <template v-for="plugin in data.format">
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
    <Button
      v-bind="buttonSave"
      :disabled="data.isReqErr || data.isRegErr ? true : false"
    />
    <Text
      v-if="data.isRegErr || data.isReqErr"
      :textClass="'setting-error'"
      :text="
        data.isReqErr
          ? $t('dashboard_advanced_required', {
              plugin: data.pluginErr,
              setting: data.settingErr,
            })
          : $t('dashboard_advanced_invalid', {
              plugin: data.pluginErr,
              setting: data.settingErr,
            })
      "
    />
  </Container>
</template>
