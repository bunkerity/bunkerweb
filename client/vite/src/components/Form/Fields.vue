<script setup>
import { defineProps } from "vue";
import Checkbox from "@components/Forms/Field/Checkbox.vue";
import Input from "@components/Forms/Field/Input.vue";
import Select from "@components/Forms/Field/Select.vue";
import Datepicker from "@components/Forms/Field/Datepicker.vue";
import Editor from "@components/Forms/Field/Editor.vue";
import { contentIndex } from "@utils/tabindex.js";
/** 
  @name Form/Fields.vue
  @description This component wraps all available fields for a form.
  @example
   { 
  columns : {"pc": 6, "tablet": 12, "mobile": 12}, 
  id:"test-check", 
  value: "yes", 
  label: "Checkbox", 
  name: "checkbox", 
  required: true, 
  hideLabel: false, 
  inpType: "checkbox",
  headerClass: "text-red-500" 
  popovers : [
    {
      text: "This is a popover text",
      iconName: "info",
    },
  ]
  }
  @param {object} setting - Setting needed to render a field.
*/

const props = defineProps({
  // id && value && method
  setting: {
    type: Object,
    required: true,
    default: {},
  },
});
</script>

<template>
  <Checkbox
    v-if="props.setting.inpType === 'checkbox'"
    :id="props.setting.id || ''"
    :columns="props.setting.columns || false"
    :value="props.setting.value"
    :popovers="props.setting.popovers || []"
    :inpType="props.setting.inpType || 'checkbox'"
    :disabled="props.setting.disabled || false"
    :required="props.setting.required || false"
    :label="props.setting.label"
    :name="props.setting.name"
    :hideLabel="props.setting.hideLabel || false"
    :containerClass="props.setting.containerClass || ''"
    :headerClass="props.setting.headerClass || ''"
    :inpClass="props.setting.inpClass || ''"
    :tabId="props.setting.tabId || contentIndex"
  />
  <Select
    v-if="props.setting.inpType === 'select'"
    :id="props.setting.id || ''"
    :columns="props.setting.columns || false"
    :value="props.setting.value"
    :values="props.setting.values"
    :inpType="props.setting.inpType || 'select'"
    :maxBtnChars="props.setting.maxBtnChars || 0"
    :disabled="props.setting.disabled || false"
    :required="props.setting.required || false"
    :requiredValues="props.setting.requiredValues || []"
    :label="props.setting.label"
    :name="props.setting.name"
    :popovers="props.setting.popovers || []"
    :onlyDown="props.setting.onlyDown || false"
    :overflowAttrEl="props.setting.overflowAttrEl || ''"
    :hideLabel="props.setting.hideLabel || false"
    :containerClass="props.setting.containerClass || ''"
    :headerClass="props.setting.headerClass || ''"
    :inpClass="props.setting.inpClass || ''"
    :tabId="props.setting.tabId || contentIndex"
  />
  <Datepicker
    v-if="props.setting.inpType === 'datepicker'"
    :id="props.setting.id || ''"
    :columns="props.setting.columns || false"
    :value="props.setting.value || ''"
    :minDate="props.setting.minDate || ''"
    :maxDate="props.setting.maxDate || ''"
    :inpType="props.setting.inpType || 'datepicker'"
    :name="props.setting.name"
    :label="props.setting.label"
    :popovers="props.setting.popovers || []"
    :isClipboard="props.setting.isClipboard || true"
    :hideLabel="props.setting.hideLabel || false"
    :containerClass="props.setting.containerClass || ''"
    :headerClass="props.setting.headerClass || ''"
    :inpClass="props.setting.inpClass || ''"
    :disabled="props.setting.disabled || false"
    :required="props.setting.required || false"
    :tabId="props.setting.tabId || contentIndex"
  />
  <Input
    v-if="props.setting.inpType === 'input'"
    :id="props.setting.id || ''"
    :columns="props.setting.columns || false"
    :name="props.setting.name"
    :type="props.setting.type"
    :inpType="props.setting.inpType || 'input'"
    :required="props.setting.required || false"
    :disabled="props.setting.disabled || false"
    :value="props.setting.value"
    :placeholder="props.setting.placeholder || ''"
    :pattern="props.setting.pattern || ''"
    :isClipboard="props.setting.isClipboard || true"
    :readonly="props.setting.readonly || false"
    :label="props.setting.label"
    :popovers="props.setting.popovers || []"
    :hideLabel="props.setting.hideLabel || false"
    :containerClass="props.setting.containerClass || ''"
    :headerClass="props.setting.headerClass || ''"
    :inpClass="props.setting.inpClass || ''"
    :tabId="props.setting.tabId || contentIndex"
  />
  <Editor
    v-if="props.setting.inpType === 'editor'"
    :id="props.setting.id || ''"
    :columns="props.setting.columns || false"
    :name="props.setting.name"
    :inpType="props.setting.inpType || 'editor'"
    :required="props.setting.required || false"
    :disabled="props.setting.disabled || false"
    :value="props.setting.value"
    :pattern="props.setting.pattern || ''"
    :isClipboard="props.setting.isClipboard || true"
    :label="props.setting.label"
    :popovers="props.setting.popovers || []"
    :hideLabel="props.setting.hideLabel || false"
    :containerClass="props.setting.containerClass || ''"
    :headerClass="props.setting.headerClass || ''"
    :editorClass="props.setting.editorClass || ''"
    :tabId="props.setting.tabId || contentIndex"
  />
</template>
