<script setup>
import { defineProps } from "vue";

/** 
  @name Forms/Header/Field.vue
  @description This component is used with field in order to link a label to field type.
  We can add popover to display more information.
  Always use with field component.
  @example
  {
    label: 'Test',
    version : "0.1.0",
    name: 'test-input',
    required: true,
  }
  @param {string} label - The label of the field. Can be a translation key or by default raw text.
  @param {string} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
  @param {boolean} [required=false]
  @param {boolean} [hideLabel=false]
  @param {string} [headerClass=""]
*/

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
    required: {
        type: Boolean,
        required: false,
    },
  version: {
    type: String,
    required: false,
  },
  hideLabel: {
    type: Boolean,
    required: false,
  },
  headerClass: {
    type: String,
    required: false,
  },
});
</script>

<template>
  <div :class="['relative', props.hideLabel ? 'hidden' : '', props.headerClass]">
    <label
      :class="[props.label ? '' : 'sr-only']"
      :for="props.name"
      class="relative lowercase capitalize-first my-1 transition duration-300 ease-in-out text-sm sm:text-md font-bold m-0 dark:text-gray-300"
    >
    {{ props.label ? $t(props.label, props.label) : $t(props.name, props.name) }} <span v-if="props.version">{{ props.version }}</span>
  </label>
  <span
    v-if="props.required"
    class="font-bold text-red-500 absolute ml-1"
    >*
  </span>
  </div>
</template>
