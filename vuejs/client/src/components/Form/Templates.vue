<script setup>
import { reactive, defineProps, computed, onBeforeMount } from "vue";
import Container from "@components/Widget/Container.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
import Advanced from "@components/Form/Advanced.vue";
import { v4 as uuidv4 } from "uuid";

/**
  @name Form/Templates.vue
  @description This component is used to create a complete  settings form with all modes (advanced, raw, easy).
  @example
  const data = {
    advanced : {
      default : [{SETTING_1}, {SETTING_2}...],
      low : [{SETTING_1}, {SETTING_2}...],
    },
    easy : {
      default : [...],
      low : [...],
    }
  }
  @param {object} templates - List of advanced templates that contains settings. Must be a dict with mode as key, then the template name as key with a list of data (different for each modes).
*/

const props = defineProps({
  // id && value && method
  templates: {
    type: Object,
    required: true,
    default: {},
  },
});

const comboboxTemplate = {
  id: uuidv4(),
  name: uuidv4(),
  disabled: false,
  required: false,
  label: "dashboard_templates",
  tabId: "1",
  columns: { pc: 4, tablet: 6, mobile: 12 },
};

const comboboxModes = {
  id: uuidv4(),
  name: uuidv4(),
  disabled: false,
  required: false,
  label: "dashboard_modes",
  tabId: "1",
  columns: { pc: 4, tablet: 6, mobile: 12 },
};

const data = reactive({
  currTemplateName: "",
  currModeName: "",
  modes: computed(() => {
    if (!props.templates) return [];
    // modes are first level keys of props.templates
    return Object.keys(props.templates);
  }),
  templates: computed(() => {
    // Get all templates available for the current mode
    if (!data.currModeName) return [];
    return Object.keys(props.templates[data.currModeName]);
  }),
});

function getFirstTemplateName() {
  return Object.keys(props.templates[data.currModeName])[0];
}

function getFirstModeName() {
  // Get first key in props.templates dict
  return Object.keys(props.templates)[0];
}

onBeforeMount(() => {
  // Get first props.templates template name
  data.currModeName = getFirstModeName();
  data.currTemplateName = getFirstTemplateName();
});
</script>

<template>
  <Container
    v-if="data.currModeName && data.currTemplateName"
    :tag="'form'"
    method="POST"
    :containerClass="`col-span-12 w-full m-1 p-1`"
    :columns="props.columns"
  >
    <Container
      v-if="data.modes.length > 0 && data.templates.length > 0"
      :containerClass="`col-span-12 grid grid-cols-12`"
    >
      <Combobox
        v-if="data.templates.length"
        v-bind="comboboxTemplate"
        :value="data.currTemplateName"
        :values="data.templates"
        @inp="data.currTemplateName = $event"
      />
      <Combobox
        v-if="data.modes.length"
        v-bind="comboboxModes"
        :value="data.currModeName"
        :values="data.modes"
        @inp="data.currModeName = $event"
      />
    </Container>
    <Advanced
      v-if="data.currModeName === 'advanced'"
      :template="props.templates[data.currModeName][data.currTemplateName]"
    />
  </Container>
</template>
