<script setup>
import { reactive, defineProps, computed, onBeforeMount } from "vue";
import Container from "@components/Widget/Container.vue";
import Grid from "@components/Widget/Grid.vue";
import Select from "@components/Forms/Field/Select.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
import Advanced from "@components/Form/Advanced.vue";
import Raw from "@components/Form/Raw.vue";
import Easy from "@components/Form/Easy.vue";
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
  templates: {
    type: Object,
    required: true,
    default: {},
  },
});

const comboboxTemplate = {
  id: `combobox-template-${uuidv4()}`,
  name: `combobox-template-${uuidv4()}`,
  disabled: false,
  maxBtnChars: 24,
  label: "dashboard_templates",
  columns: { pc: 3, tablet: 12, mobile: 12 },
  containerClass: "setting",
  popovers: [
    {
      text: "inp_templates_desc",
      iconName: "info",
    },
  ],
};

const comboboxModes = {
  id: `combobox-modes-${uuidv4()}`,
  name: `combobox-modes-${uuidv4()}`,
  disabled: false,
  required: false,
  onlyDown: true,
  maxBtnChars: 24,
  label: "dashboard_modes",
  columns: { pc: 3, tablet: 12, mobile: 12 },
  containerClass: "setting",
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
    :containerClass="`col-span-12 w-full`"
    :columns="props.columns"
  >
    <Grid
      :gridClass="'layout-settings'"
      v-if="data.modes.length > 1 || data.templates.length > 1"
    >
      <Combobox
        v-if="data.templates.length > 1"
        v-bind="comboboxTemplate"
        :value="data.currTemplateName"
        :values="data.templates"
        @inp="data.currTemplateName = $event"
      />
      <Select
        v-if="data.modes.length > 1"
        v-bind="comboboxModes"
        :value="data.currModeName"
        :values="data.modes"
        @inp="data.currModeName = $event"
      />
    </Grid>
    <Advanced
      v-if="data.currModeName === 'advanced'"
      :template="props.templates[data.currModeName][data.currTemplateName]"
    />
    <Raw
      v-if="data.currModeName === 'raw'"
      :template="props.templates[data.currModeName][data.currTemplateName]"
    />
    <Easy
      v-if="data.currModeName === 'easy'"
      :template="props.templates[data.currModeName][data.currTemplateName]"
    />
  </Container>
</template>
