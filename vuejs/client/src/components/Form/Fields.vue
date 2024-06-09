<script setup>
import { reactive, defineProps, onMounted, ref } from "vue";
import Checkbox from "@components/Forms/Field/Checkbox.vue";
import Input from "@components/Forms/Field/Input.vue";
import Select from "@components/Forms/Field/Select.vue";
import Datepicker from "@components/Forms/Field/Datepicker.vue";

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
      iconColor: "info",
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
    v-bind="props.setting"
  />
  <Select v-if="props.setting.inpType === 'select'" v-bind="props.setting" />
  <Datepicker
    v-if="props.setting.inpType === 'datepicker'"
    v-bind="props.setting"
  />
  <Input v-if="props.setting.inpType === 'input'" v-bind="props.setting" />
</template>
