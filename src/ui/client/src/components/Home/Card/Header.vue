<script setup>
import { defineProps } from "vue";

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  count: {
    type: [Number, String],
    required: true,
  },
});
</script>

<template>
  <h2 class="card-stat-title">{{ props.name ? props.name : "none" }}</h2>
  <p class="card-stat-count">
    {{ props.count ? props.count : "none" }}
  </p>
</template>
