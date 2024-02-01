<script setup>
const props = defineProps({
  title: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <div>
    <p v-if="props.title" class="modal-card-title">{{ props.title }}</p>
    <slot></slot>
  </div>
</template>
