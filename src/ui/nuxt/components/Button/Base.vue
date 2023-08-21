<script setup>
const props = defineProps({
  valid: {
    type: Boolean,
  },
  delete: {
    type: Boolean,
  },
  info: {
    type: Boolean,
  },
});
</script>

<template>
  <button
    :class="[
      props.valid ? 'valid-btn' : '',
      props.delete ? 'delete-btn' : '',
      props.info ? 'info-btn' : '',
    ]"
  >
    <slot></slot>
  </button>
</template>
