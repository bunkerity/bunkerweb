<script setup>
import { defineProps, reactive, onMounted, onBeforeMount, watch } from "vue";
import Container from "@components/Widget/Container.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Editor from "@components/Forms/Field/Editor.vue";
import Button from "@components/Widget/Button.vue";
import Text from "@components/Widget/Text.vue";
import { v4 as uuidv4 } from "uuid";
import { useRawForm } from "@store/form.js";

/**
 *  @name Form/Raw.vue
 *  @description This component is used to create a complete raw form with settings as JSON format.
 *  @example
 *   {
 *    "IS_LOADING": "no",
 *    "NGINX_PREFIX": "/etc/nginx/",
 *    "HTTP_PORT": "8080",
 *    "HTTPS_PORT": "8443",
 *    "MULTISITE": "yes"
 *   }
 *  @param {object} template - Template object with plugin and settings data.
 *  @param {string} [operation="edit"] - Operation type (edit, new, delete).
 *  @param {string} [oldServerName=""] - Old server name. This is a server name before any changes.
 *  @param {string} containerClass - Container
 *  @param {object} columns - Columns object.
 */

const rawForm = useRawForm();

const props = defineProps({
  // id && value && method
  template: {
    type: Object,
    required: true,
    default: {},
  },
  operation: {
    type: String,
    required: false,
    default: "edit",
  },
  oldServerName: {
    type: String,
    required: false,
    default: "",
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
  isValid: true,
  // This will be use to unmount and remount the editor (create a new editor instance because it is vanilla js)
  isRender: true,
});

watch(
  () => props.template,
  () => {
    // Unmount editor
    data.isRender = false;
    // Prepare data
    rawForm.setRawData(json2raw(props.template), true);
    updateRaw(rawForm.rawData);
    rawForm.setOperation(props.operation);
    rawForm.setOldServerName(props.oldServerName);
    // Remount, wait some time to be sure the editor is unmounted
    setTimeout(() => {
      data.isRender = true;
    }, 50);
  },
);

/**
 *  @name updateRaw
 *  @description Get the raw data from editor, update the raw store with it and check if it is valid JSON.
 *  @param {string} v - The raw data to update.
 *  @returns {void}
 */
function updateRaw(v) {
  // Transform to a possible valid JSON
  rawForm.setRawData(v, true);
  let dataToCheck = v;
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

  if (!isValidRaw) return (data.isValid = false);

  // Try to parse the JSON
  jsonReady = "{" + jsonReady.slice(0, -1) + "}";

  try {
    const json = JSON.parse(jsonReady);
    rawForm.setTemplate(json, true);
    data.isValid = true;
  } catch (e) {
    console.error(e);
    data.isValid = false;
  }
}

/**
 *  @name json2raw
 *  @description Convert a JSON object to a raw string that can be passed to the editor.
 *  This will convert JSON to key value pairs (format key=value).
 *  This is only used at first mount when there is no raw data.
 *  @param {string} json  - The template json to convert
 *  @returns {string} - The raw string
 */
function json2raw(json) {
  // return nothing case json is empty object
  if (Object.keys(json).length === 0) return "";

  let dataStr = JSON.stringify(json);
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
}

const editorData = {
  name: `raw-editor-${uuidv4()}`,
  label: `raw-editor-${uuidv4()}`,
  hideLabel: true,
  columns: { pc: 12, tablet: 12, mobile: 12 },
  editorClass: "min-h-96",
};

const buttonSave = {
  id: `raw-save-${uuidv4()}`,
  text: "action_save",
  color: "success",
  size: "normal",
  containerClass: "flex justify-center",
};

onBeforeMount(() => {
  rawForm.setRawData(json2raw(props.template));
});

onMounted(() => {
  rawForm.setOperation(props.operation);
  rawForm.setOldServerName(props.oldServerName);
});
</script>

<template>
  <Container
    data-raw-
    data-is="form"
    :tag="'form'"
    method="POST"
    :containerClass="'form-raw-container'"
    :columns="props.columns"
  >
    <Title type="card" :title="'dashboard_raw_mode'" />
    <Subtitle type="card" :subtitle="'dashboard_raw_mode_subtitle'" />

    <Container class="form-raw-editor-container layout-settings">
      <Editor
        v-if="data.isRender"
        @inp="(v) => updateRaw(v)"
        v-bind="editorData"
        :value="rawForm.rawData"
      />
    </Container>
    <Button
      @click="rawForm.submit()"
      :disabled="data.isValid ? false : rawForm.isUpdateData ? false : true"
      v-bind="buttonSave"
    />

    <div class="flex justify-center items-center" data-is="form-error">
      <Text
        v-if="!data.isValid"
        :text="'dashboard_raw_invalid'"
        :textClass="'form-setting-error'"
      />
    </div>
  </Container>
</template>
