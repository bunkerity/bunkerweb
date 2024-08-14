<script setup>
import { defineProps } from "vue";
import Checkbox from "@components/Forms/Field/Checkbox.vue";
import Input from "@components/Forms/Field/Input.vue";
import Select from "@components/Forms/Field/Select.vue";
import Datepicker from "@components/Forms/Field/Datepicker.vue";
import Editor from "@components/Forms/Field/Editor.vue";
import { contentIndex } from "@utils/tabindex.js";
/**
 *  @name Form/Fields.vue
 *  @description This component wraps all available fields for a form.
 *  @example
 *   {
 *    columns : {"pc": 6, "tablet": 12, "mobile": 12},
 *    id:"test-check",
 *    value: "yes",
 *    label: "Checkbox",
 *    name: "checkbox",
 *    required: true,
 *    hideLabel: false,
 *    inpType: "checkbox",
 *    headerClass: "text-red-500"
 *    popovers : [
 *      {
 *        text: "This is a popover text",
 *        iconName: "info",
 *      },
 *    ]
 *  }
 *  @param {Object} setting - Setting needed to render a field.
 */

const props = defineProps({
  // id && value && method
  setting: {
    type: Object,
    required: true,
    default: {},
  },
});

/**
 *  @name getDataByField
 *  @description Retrieve share data and specific data for each fields in order to v-bind.
 *  @param {Object} setting - Setting props
 *  @param {String} fallbackInpType - The fallback to add fallback in some cases.
 *  @returns {Object} - props object
 */
function getDataByField(setting, fallbackInpType) {
  console;
  // Start by the base = setting share by all fields
  const base = {
    inpType: setting?.inpType || fallbackInpType,
    id: setting?.id || "",
    columns: setting?.columns || { pc: "12", tablet: "12", mobile: "12" },
    value: setting?.value || "",
    popovers: setting?.popovers || [],
    disabled: setting?.disabled || false,
    required: setting?.required || false,
    label: setting?.label || null,
    name: setting?.name || null,
    hideLabel: setting?.hideLabel || false,
    containerClass: setting?.containerClass || "",
    headerClass: setting?.headerClass || "",
    inpClass: setting?.inpClass || "",
    tabId: setting?.tabId || contentIndex,
    attrs: setting?.attrs || {},
    fieldSize: setting?.fieldSize || "normal",
    hideFeedbackError: setting?.hideFeedbackError || false,
  };

  if (
    setting?.inpType === "select" ||
    (!setting?.inpType && fallbackInpType === "select")
  ) {
    base["values"] = setting?.values || [];
    base["maxBtnChars"] = setting?.maxBtnChars || 0;
    base["requiredValues"] = setting?.requiredValues || [];
    base["onlyDown"] = setting?.onlyDown || false;
    base["overflowAttrEl"] = setting?.overflowAttrEl || "";
  }

  if (
    setting?.inpType === "datepicker" ||
    (!setting?.inpType && fallbackInpType === "datepicker")
  ) {
    base["minDate"] = setting?.minDate || "";
    base["maxDate"] = setting?.maxDate || "";
    base["isClipboard"] = setting?.isClipboard || false;
  }

  if (
    setting?.inpType === "input" ||
    (!setting?.inpType && fallbackInpType === "input")
  ) {
    base["type"] = setting?.type || "text";
    base["placeholder"] = setting?.placeholder || "";
    base["pattern"] = setting?.pattern || "";
    base["isClipboard"] = setting?.isClipboard || false;
    base["readonly"] = setting?.readonly;
  }

  if (
    setting?.inpType === "editor" ||
    (!setting?.inpType && fallbackInpType === "editor")
  ) {
    base["pattern"] = setting?.pattern || "";
    base["isClipboard"] = setting?.isClipboard || false;
  }

  return base;
}

// emits
const emit = defineEmits(["inp"]);
</script>

<template>
  <Checkbox
    @inp="(value) => $emit('inp', value)"
    v-if="props.setting.inpType === 'checkbox'"
    v-bind="{ ...getDataByField(props.setting, 'checkbox') }"
  />
  <Select
    @inp="(value) => $emit('inp', value)"
    v-if="props.setting.inpType === 'select'"
    v-bind="{ ...getDataByField(props.setting, 'select') }"
  />
  <Datepicker
    @inp="(value) => $emit('inp', value)"
    v-if="props.setting.inpType === 'datepicker'"
    v-bind="{ ...getDataByField(props.setting, 'datepicker') }"
  />
  <Input
    @inp="(value) => $emit('inp', value)"
    v-if="props.setting.inpType === 'input'"
    v-bind="{ ...getDataByField(props.setting, 'input') }"
  />
  <Editor
    @inp="(value) => $emit('inp', value)"
    v-if="props.setting.inpType === 'editor'"
    v-bind="{ ...getDataByField(props.setting, 'editor') }"
  />
</template>
