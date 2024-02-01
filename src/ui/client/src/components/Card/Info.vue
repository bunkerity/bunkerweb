<script setup>
import CardBase from "@components/Card/Base.vue";
import CardLabel from "@components/Card/Label.vue";
import { defineProps } from "vue";

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  text: {
    type: String,
    required: true,
  },
});
</script>

<template>
  <CardBase>
    <CardLabel v-if="props.label" :label="props.label" />
    <p class="card-info-text">{{ props.text }}</p>
  </CardBase>
</template>
