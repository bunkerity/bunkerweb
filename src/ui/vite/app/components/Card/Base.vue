<script setup>
import CardLabel from "../Card/Label.vue";
const props = defineProps({
  label: {
    type: String,
    required: false,
  },
  // default || error
  color: {
    type: String,
    required: false,
    default: "default",
  },
});
</script>

<template>
  <div :class="[`${props.color}`]" class="card grid grid-cols-12">
    <div class="col-span-12 grid grid-cols-12 justify-start">
      <CardLabel v-if="props.label" :label="props.label" />
      <slot></slot>
    </div>
  </div>
</template>
