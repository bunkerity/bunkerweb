<script setup>
import { defineProps } from "vue";

const props = defineProps({
  // valid || delete || info
  color: {
    type: String,
  },
  // sm || normal || lg || xl
  size: {
    type: String,
  },
});
</script>

<template>
  <button :class="[`btn btn-${props.color} btn-${props.size}`]">
    <slot></slot>
  </button>
</template>
