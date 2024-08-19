<script setup>
import { reactive, defineProps, computed, onBeforeMount, watch } from "vue";
import Container from "@components/Widget/Container.vue";
import Grid from "@components/Widget/Grid.vue";
import Select from "@components/Forms/Field/Select.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
import Advanced from "@components/Form/Advanced.vue";
import Raw from "@components/Form/Raw.vue";
import Easy from "@components/Form/Easy.vue";
import { v4 as uuidv4 } from "uuid";
import { useDisplayStore } from "@store/global.js";

/**
 *  @name Form/Templates.vue
 *  @description This component is used to create a complete  settings form with all modes (advanced, raw, easy).
 *  @example
 *  {
 *    advanced : {
 *      default : [{SETTING_1}, {SETTING_2}...],
 *      low : [{SETTING_1}, {SETTING_2}...],
 *    },
 *    easy : {
 *      default : [...],
 *      low : [...],
 *    }
 *  }
 * @param {Object} templates - List of advanced templates that contains settings. Must be a dict with mode as key, then the template name as key with a list of data (different for each modes).
 * @param {String} [operation="edit"] - Operation type (edit, new, delete).
 * @param {String} [oldServerName=""] - Old server name. This is a server name before any changes.
 * @param {String|Boolean} [isDraft=false] - Is draft mode. "yes" or "no" to set a draft select. Else will be ignored.
 * @param {Array} [display=[]] - Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef.
 */

const props = defineProps({
  templates: {
    type: Object,
    required: true,
    default: {},
  },
  operation: {
    type: String,
    required: false,
    default: "edit",
  },
  isDraft: {
    type: [String, Boolean],
    required: false,
    default: false,
  },
  oldServerName: {
    type: String,
    required: false,
    default: "",
  },
  display: {
    type: Array,
    required: false,
    default: [],
  },
});

const displayStore = useDisplayStore();

const comboboxTemplate = {
  id: `combobox-template-${uuidv4()}`,
  name: `combobox-template-${uuidv4()}`,
  disabled: false,
  maxBtnChars: 24,
  label: "dashboard_templates",
  columns: { pc: 3, tablet: 12, mobile: 12 },
  containerClass: "setting",
  onlyDown: true,
  popovers: [
    {
      text: "inp_templates_desc",
      iconName: "info",
    },
  ],
};

const draftSelect = {
  id: `draft-select-${uuidv4()}`,
  name: `draft-select-${uuidv4()}`,
  disabled: false,
  required: false,
  onlyDown: true,
  maxBtnChars: 24,
  value: props.isDraft,
  values: ["yes", "no"],
  containerClass: "setting",
  label: "dashboard_draft",
  popovers: [
    {
      text: "dashboard_draft_desc",
      iconName: "info",
    },
  ],
  columns: { pc: 3, tablet: 12, mobile: 12 },
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
  isDisplay: props.display.length
    ? displayStore.isCurrentDisplay(props.display[0], props.display[1])
    : true,
});

/**
 *  @name checkDisplay
 *  @description Check if the current display value is matching the display store value.
 *  @returns {Void}
 */
function checkDisplay() {
  if (!props.display.length) return;
  data.isDisplay = displayStore.isCurrentDisplay(
    props.display[0],
    props.display[1]
  );
}

// Case we have set a display group name and component id, the component id must match the current display id for the same group name to be displayed.
if (props.display.length) {
  watch(displayStore.display, (val) => {
    checkDisplay();
  });
}
/**
 *  @name getFirstTemplateName
 *  @description Get the first template name from the first mode.
 *  @returns {string} - The first template name
 */
function getFirstTemplateName() {
  return Object.keys(props.templates[data.currModeName])[0];
}

/**
 *  @name getFirstTemplateName
 *  @description Get the first mode name from the first key in props.templates dict.
 *  @returns {string} - The first mode name
 */
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
    v-if="data.isDisplay && data.currModeName && data.currTemplateName"
    :containerClass="`col-span-12 w-full ${
      data.templates.length > 1 ? '' : 'mb-3'
    }`"
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
      <Select data-draft-state v-if="props.isDraft" v-bind="draftSelect" />
    </Grid>
    <Advanced
      v-if="data.currModeName === 'advanced'"
      :template="props.templates[data.currModeName][data.currTemplateName]"
      :operation="props.operation"
      :oldServerName="props.oldServerName"
    />
    <Raw
      v-if="data.currModeName === 'raw'"
      :template="props.templates[data.currModeName][data.currTemplateName]"
      :operation="props.operation"
      :oldServerName="props.oldServerName"
    />
    <Easy
      v-if="data.currModeName === 'easy'"
      :template="props.templates[data.currModeName][data.currTemplateName]"
      :operation="props.operation"
      :oldServerName="props.oldServerName"
    />
  </Container>
</template>
