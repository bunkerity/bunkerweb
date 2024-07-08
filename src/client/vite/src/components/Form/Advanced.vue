<script setup>
import { defineProps, reactive, onMounted, onUnmounted } from "vue";
import MessageUnmatch from "@components/Message/Unmatch.vue";
import Container from "@components/Widget/Container.vue";
import Fields from "@components/Form/Fields.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
import Button from "@components/Widget/Button.vue";
import Text from "@components/Widget/Text.vue";
import Filter from "@components/Widget/Filter.vue";
import GroupMultiple from "@components/Forms/Group/Multiple.vue";
import { plugin_types } from "@utils/variables";

import {
  useCheckPluginsValidity,
  useUpdateTempSettings,
  useListenTemp,
  useUnlistenTemp,
} from "@utils/form.js";
import { v4 as uuidv4 } from "uuid";
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
    default: { pc: 12, tablet: 12, mobile: 12 },
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

const comboboxPlugin = {
  id: `advanced-combobox-${uuidv4()}`,
  name: `advanced-combobox-${uuidv4()}`,
  disabled: false,
  required: false,
  onlyDown: true,
  maxBtnChars: 24,
  containerClass: "setting",
  label: "dashboard_plugins",
  popovers: [
    {
      text: "inp_combobox_advanced_desc",
      iconName: "info",
    },
  ],
  columns: { pc: 3, tablet: 12, mobile: 12 },
};

const buttonSave = {
  id: `advanced-save-${uuidv4()}`,
  text: "action_save",
  color: "success",
  size: "normal",
  type: "button",
  attrs: {
    "data-submit-form": JSON.stringify(data.base),
  },
  containerClass: "flex justify-center",
  iconName: "plus",
};

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
      id: `advanced-filter-keyword-${uuidv4()}`,
      value: "",
      type: "text",
      name: `advanced-filter-keyword-${uuidv4()}`,
      containerClass: "setting",
      label: "inp_search_settings",
      placeholder: "inp_keyword",
      isClipboard: false,
      popovers: [
        {
          text: "inp_search_settings_desc",
          iconName: "info",
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
      id: `advanced-filter-type-${uuidv4()}`,
      value: "all",
      // add 'all' as first value
      values: ["all"].concat(plugin_types),
      name: `advanced-filter-type-${uuidv4()}`,
      onlyDown: true,
      label: "inp_select_plugin_type",
      containerClass: "setting",
      maxBtnChars: 24,
      popovers: [
        {
          text: "inp_select_plugin_type_desc",
          iconName: "info",
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
      id: `advanced-filter-context-${uuidv4()}`,
      value: "all",
      // add 'all' as first value
      values: ["all", "multisite", "global"],
      name: `advanced-filter-context-${uuidv4()}`,
      onlyDown: true,
      containerClass: "setting",
      label: "inp_select_plugin_context",
      maxBtnChars: 24,
      popovers: [
        {
          text: "inp_select_plugin_context_desc",
          iconName: "info",
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
    data-is="form"
    :tag="'form'"
    method="POST"
    :containerClass="`form-advanced-container`"
    :columns="props.columns"
  >
    <Title type="card" :title="'dashboard_advanced_mode'" />
    <Subtitle type="card" :subtitle="'dashboard_advanced_mode_subtitle'" />
    <Filter
      v-if="filters.length"
      @filter="(v) => filter(v)"
      :data="data.base"
      :filters="filters"
    >
      <Combobox
        v-bind="comboboxPlugin"
        :value="data.currPlugin"
        :values="data.plugins"
        @inp="data.currPlugin = $event"
      />
    </Filter>
    <MessageUnmatch v-if="!data.format.length" />
    <template v-for="plugin in data.format">
      <Container
        data-is="content"
        data-advanced-form-plugin
        v-if="plugin.name === data.currPlugin"
        class="form-advanced-plugin-container"
      >
        <Title type="content" :title="plugin.name" />
        <Subtitle type="content" :subtitle="plugin.description" />

        <Container class="layout-settings">
          <template
            v-for="(setting, name, index) in plugin.settings"
            :key="index"
          >
            <Fields :setting="setting" />
          </template>
        </Container>
        <GroupMultiple v-if="plugin.multiples" :multiples="plugin.multiples" />
      </Container>
    </template>
    <Button
      v-if="data.format.length"
      v-bind="buttonSave"
      :disabled="data.isReqErr || data.isRegErr ? true : false"
    />
    <div class="flex justify-center items-center" data-is="form-error">
      <Text
        v-if="
          (data.format.length && data.isRegErr) ||
          (data.format.length && data.isReqErr)
        "
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
    </div>
  </Container>
</template>
