<script setup>
import { defineProps } from "vue";

/* PROPS ARGUMENTS
  *
  *
  label: string,
  name: string,
  required: boolean,
  version: string,
  hideLabel: boolean,
  required: boolean,
  headerClass: string,
  *
  *
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
    {{ props.label ? props.label : props.name }} <span v-if="props.version">{{ props.version }}</span>
  </label>
  <span
    v-if="props.required"
    class="font-bold text-red-500 absolute ml-1"
    >*
  </span>
  </div>
</template>
