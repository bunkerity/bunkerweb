<script setup>
import { defineProps, reactive, onMounted, computed } from "vue";
import Container from "@components/Widget/Container.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Editor from "@components/Forms/Field/Editor.vue";
import Button from "@components/Widget/Button.vue";
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
    default: {},
  },
});

const data = reactive({
  format: computed(() => {
    const dataStr = JSON.stringify(props.template);
    // Add a new line after the comma
    return dataStr.replace(/,/g, ",\n");
  }),
});

const editorData = {
  value: data.format,
  name: "test-editor",
  label: "Test editor",
  columns: { pc: 12, tablet: 12, mobile: 12 },
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
</script>

<template>
  <Container
    :tag="'form'"
    method="POST"
    :containerClass="`col-span-12 w-full m-1 p-1`"
    :columns="props.columns"
  >
    <Title type="card" :title="'dashboard_raw_mode'" />
    <Subtitle type="card" :subtitle="'dashboard_raw_mode_subtitle'" />
    <Container class="col-span-12 w-full">
      <Editor v-bind="editorData" />
    </Container>
    <Button v-bind="buttonSave" />
  </Container>
</template>
