<script setup>
import { reactive, defineProps, onMounted, ref } from "vue";
import Container from "@components/Widget/Container.vue";
import Fields from "@components/Form/Fields.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
import { v4 as uuidv4 } from "uuid";

/**
  @name Form/Settings.vue
  @description This component is used to create a complete  settings form with all modes (advanced, raw, easy).
  @example
  const data = [
    {
      name: "plugin name",
      type: "pro",
      description: "plugin description",
      page: "/page",
      settings: [
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
    },
  ];
  @param {object} templates - List of advanced templates that contains settings.
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

const data = reactive({
  currTemplate: "",
  currPlugin: "",
});

function getFirstTemplate() {
  return Object.keys(props.templates)[0];
}

function getTemplateNames() {
  return Object.keys(props.templates);
}

onMounted(() => {
  // Get first props.templates template name
  data.currTemplate = getFirstTemplate();
});
</script>

<template>
  <Container
    :tag="'form'"
    method="POST"
    :containerClass="`col-span-12 w-full m-1 p-1`"
    :columns="props.columns"
  >
    <template v-for="(template, template_name) in props.templates">
      <Container :containerClass="`col-span-12 grid grid-cols-12`">
        <Combobox
          v-bind="comboboxTemplate"
          :value="getFirstTemplate()"
          :values="getTemplateNames()"
          @inp="data.currPlugin = $event"
        />
      </Container>
    </template>
  </Container>
</template>
