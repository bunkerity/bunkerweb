<script setup>
import { defineProps, reactive, onMounted, computed } from "vue";
import Container from "@components/Widget/Container.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Editor from "@components/Forms/Field/Editor.vue";
import Button from "@components/Widget/Button.vue";
import Text from "@components/Widget/Text.vue";
import { v4 as uuidv4 } from "uuid";

/**
  @name Form/RAW.vue
  @description This component is used to create a complete raw form with settings as JSON format.
  @example
  {
   "IS_LOADING": "no",
   "NGINX_PREFIX": "/etc/nginx/", 
   "HTTP_PORT": "8080", 
   "HTTPS_PORT": "8443", 
   "MULTISITE": "yes" 
  }
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
  str: JSON.stringify(props.template),
  // Data on creation of editor
  entry: computed(() => {
    // TODO : WORK WITH LINE LOOP
    // ONLY REPLACE FIRST ':' IS REPLACED (IN CASE VALUE CONTAIN ':')
    let dataStr = data.str;
    // Remove first and last curly brackets
    dataStr = dataStr.slice(1, -1);
    // Remove all '\"' from stringified JSON
    dataStr = dataStr.replace(/\\"/g, '"');
    // Remove all newlines inside values
    dataStr = dataStr.replace(/\n/g, "");
    // Add new line only at the end of each key value
    dataStr = dataStr.replace(/",/g, "\n");

    const lines = dataStr.split("\n");
    dataStr = lines.map((line) => {
      // Get index of the first colon
      const index = line.indexOf(":");
      // Update colon by equal sign and remove quotes
      return line.slice(1, index - 1) + "=" + line.slice(index + 2);
    });
    dataStr = dataStr.join("\n");
    // Remove first char if it is a quote
    dataStr = dataStr[0] === '"' ? dataStr.slice(1) : dataStr;
    // Remove last char if it is a quote
    dataStr = dataStr.slice(-1) === '"' ? dataStr.slice(0, -1) : dataStr;

    return dataStr;
  }),
  // Data retrieve from editor after creation
  inp: "",
  isValid: computed(() => {
    // Transform to a possible valid JSON
    let dataToCheck = data.inp || data.entry;
    // Replace quotes "" with quotes ''
    dataToCheck = dataToCheck.replace(/"/g, "'");

    let isValidRaw = true;
    let jsonReady = "";

    // loop on each line
    dataToCheck = dataToCheck.split("\n");
    dataToCheck = dataToCheck.map((line) => {
      // Get index of the first equal sign
      const index = line.indexOf("=");
      // Case no equal sign in a line, this is invalid
      if (index === -1) isValidRaw = false;

      // Update at this index with a colon
      jsonReady +=
        '"' + line.slice(0, index) + '":"' + line.slice(index + 1) + '",';
    });

    if (!isValidRaw) return false;

    // Try to parse the JSON
    jsonReady = "{" + jsonReady.slice(0, -1) + "}";

    try {
      JSON.parse(jsonReady);
      return true;
    } catch (e) {
      console.log(e);
      return false;
    }
  }),
});

const editorData = {
  value: data.inp || data.entry,
  name: uuidv4(),
  label: uuidv4(),
  hideLabel: true,
  columns: { pc: 12, tablet: 12, mobile: 12 },
  editorClass: "min-h-96",
};

const buttonSave = {
  id: uuidv4(),
  text: "action_save",
  color: "success",
  size: "normal",
  containerClass: "flex justify-center",
  attrs: data.isValid
    ? {
        "data-submit-form":
          data.inp.replace(/\n/g, "") || data.entry.replace(/\n/g, ""),
      }
    : {},
};
</script>

<template>
  <Container
    :tag="'form'"
    method="POST"
    :containerClass="`col-span-12 w-full m-1 p-1`"
    :columns="props.columns"
  >
    {{ data.isValid ? "Valid" : "Not Valid" }}
    <Title type="card" :title="'dashboard_raw_mode'" />
    <Subtitle type="card" :subtitle="'dashboard_raw_mode_subtitle'" />
    <Container class="col-span-12 w-full">
      <Editor @inp="(v) => (data.inp = v)" v-bind="editorData" />
    </Container>
    <Button :disabled="data.isValid ? false : true" v-bind="buttonSave" />
    <Text
      v-if="!data.isValid"
      :text="'dashboard_raw_invalid'"
      :textClass="'text-center error'"
    />
  </Container>
</template>
