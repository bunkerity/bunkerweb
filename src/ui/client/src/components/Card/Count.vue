<script setup>
import { defineProps } from "vue";
import { contentIndex } from "@utils/tabindex.js";

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  count: {
    type: [Number, String],
    required: false,
  },
  detail: {
    type: String,
    required: false,
  },
  // default || error || success || warning || info
  detailColor: {
    type: String,
    required: false,
    default: "default",
  },
});

const colors = {
  success: "text-green-500",
  error: "text-red-500",
  warning: "text-yellow-500",
  info: "text-sky-500",
  default: "text-gray-700 dark:text-gray-500",
};
</script>

<template>
  <div
    v-if="props.label"
    :tabindex="contentIndex"
    :href="props.href ? props.href : '#'"
    class="card-count"
  >
    <div>
      <h2 class="card-count-title">{{ props.label ? props.label : "none" }}</h2>
      <p class="card-count-count">
        {{ props.count ? props.count : "unknown" }}
      </p>
      <span
        v-if="props.detail"
        :class="[colors[props.detailColor]]"
        class="card-count-detail-container-item"
      >
        {{ props.detail }}
      </span>
    </div>
    <slot></slot>
  </div>
</template>
