<script setup>
import { defineProps } from "vue";

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  count: {
    type: Number,
    required: true,
  },
});
</script>

<template>
  <p class="card-stat-title">{{ props.name ? props.name : "none" }}</p>
  <h5 class="card-stat-count">
    {{ props.count ? props.count : "none" }}
  </h5>
</template>
