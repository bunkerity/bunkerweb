<script setup>
import { defineProps } from "vue";

// Easy way wrapper to display / hidden folder children
// Check if given path === currPath to display
const props = defineProps({
  // Component path
  path: {
    type: String,
    required: true,
  },
  // Active path
  currPath: {
    type: String,
    required: true,
  },
});
</script>
<template>
  <div
    :aria-current="props.path === props.currPath ? 'true' : 'false'"
    v-if="props.path === props.currPath"
    class="w-full grid grid-cols-12 gap-4 mt-4"
  >
    <slot></slot>
  </div>
</template>
