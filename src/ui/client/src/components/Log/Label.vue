<script setup>
import { onMounted, reactive, ref } from "vue";

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
});
</script>

<template>
  <label :for="props.name" class="log-label">
    {{ props.label }}
  </label>
</template>
