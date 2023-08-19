<script setup>
const props = defineProps({
  label: {
    type: String,
    required: false,
  },
});
</script>

<template>
  <div class="card grid grid-cols-12">
    <div class="col-span-12 grid grid-cols-12 justify-start">
      <CardLabel v-if="props.label" :label="props.label" />
      <slot></slot>
    </div>
  </div>
</template>
