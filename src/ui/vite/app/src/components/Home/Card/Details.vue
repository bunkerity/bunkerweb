<script setup>
import { defineProps } from "vue";

const props = defineProps({
  detailArr: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <span
    v-for="detail in props.detailArr"
    class="card-stat-detail-container-item"
  >
    <span
      v-if="detail.num"
      :class="[
        detail.numClass ? detail.numClass : 'text-gray-700 dark:text-gray-500',
      ]"
    >
      {{ detail.num }}
    </span>
    <span
      v-if="detail.text"
      :class="[
        detail.textClass
          ? detail.textClass
          : 'text-gray-700 dark:text-gray-500',
      ]"
    >
      {{ ` ${detail.text}` }}
    </span>
  </span>
</template>
