<script setup>
const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  // In order to show / hide if active one match plugin name
  activePlugin: {
    type: String,
    required: true,
  },
});
</script>

<template>
  <div v-if="props.name === props.activePlugin" :id="props.id" class="w-full">
    <slot></slot>
  </div>
</template>
