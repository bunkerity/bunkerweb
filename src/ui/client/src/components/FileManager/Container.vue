<script setup>
import { defineProps } from "vue";
import { useModalStore } from "@store/configs.js";

const modalStore = useModalStore();
// Easy way wrapper to display / hidden folder children
// Check if given path === currPath to display
const props = defineProps({
  // Component path
  path: {
    type: String,
    required: true,
  },
});
</script>
<template>
  <div
    :aria-current="props.path === modalStore.data.path ? 'true' : 'false'"
    :aria-hidden="props.path === modalStore.data.path ? 'false' : 'true'"
    v-if="props.path === modalStore.data.path"
    class="w-full grid grid-cols-12 gap-4 mt-4"
  >
    <slot></slot>
  </div>
</template>
