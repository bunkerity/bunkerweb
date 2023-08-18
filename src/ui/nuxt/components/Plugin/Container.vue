<script setup>
const props = defineProps({
  id: {
    type: String,
    required: true,
  },
});
</script>

<template>
  <div :id="props.id" class="w-full">
    <slot></slot>
  </div>
</template>
