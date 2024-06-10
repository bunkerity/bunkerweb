<script setup>
import { defineProps, reactive, onMounted } from "vue";
import Container from "@components/Widget/Container.vue";
import Fields from "@components/Form/Fields.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
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
});

function getFirstPlugin(form) {
  return form[0]["name"];
}

function getPluginNames(form) {
  const pluginNames = [];
  // Loop on each dict from form list
  for (const plugin of form) {
    // Return the first plugin
    pluginNames.push(plugin.name);
  }
  return pluginNames;
}

const comboboxPlugin = {
  id: uuidv4(),
  name: uuidv4(),
  disabled: false,
  required: false,
  label: "dashboard_plugins",
  tabId: "1",
  columns: { pc: 4, tablet: 6, mobile: 12 },
};

onMounted(() => {
  // Get first props.forms template name
  data.currPlugin = getFirstPlugin(props.template);
});
</script>

<template>
  <Container
    :tag="'form'"
    method="POST"
    :containerClass="`col-span-12 w-full m-1 p-1`"
    :columns="props.columns"
  >
    <Container :containerClass="`grid grid-cols-12 col-span-12 w-full m-1 p-1`">
      <Combobox
        v-bind="comboboxPlugin"
        :value="getFirstPlugin(props.template)"
        :values="getPluginNames(props.template)"
        @inp="data.currPlugin = $event"
      />
    </Container>
    <template v-for="plugin in props.template">
      <Container
        v-if="plugin.name === data.currPlugin"
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
  </Container>
</template>
