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
  <div class="modal-container">
    <div class="modal-wrap">
      <div class="modal-card">
        <div v-if="props.title" class="w-full flex justify-between">
          <p class="modal-card-title">{{ props.title }}</p>
        </div>
        <slot></slot>
      </div>
    </div>
  </div>
</template>
