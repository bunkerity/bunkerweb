<script setup>
import { computed } from "vue";
/**
  @name Widget/Title.vue
  @description This component is a general title wrapper.
    @example
  {
    title: "Total Users",
    type: "card",
    titleClass: "text-lg",
    titleColor : "info",
    tag: "h2"
  }
  @param {string} title -  Can be a translation key or by default raw text.
  @param {string} type - The type of title between "card", "container" or "stat"
  @param {string} [tag=""] - The tag of the title. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of title.
  @param {string} [titleColor=""] - The color of the title between error, success, warning, info or tailwind color
  @param {string} [titleClass=""] - Additional class, useful when component is used directly on a grid system
*/

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  type: {
    type: String,
    required: false,
    default: "card",
  },
  tag: {
    type: String,
    required: false,
    default: "",
  },
  titleColor: {
    type: String,
    required: false,
    default: "",
  },
  titleClass: {
    type: String,
    required: false,
    default: "",
  },
});

const tag = computed(() => {
  if (props.tag) return props.tag;
  if (props.type === "container") return "h1";
  if (props.type === "card") return "h2";
  if (props.type === "stat") return "p";
});

const baseClass = computed(() => {
  if (props.type === "container") return "title-container";
  if (props.type === "card") return "title-card";
  if (props.type === "stat") return "title-stat";
  return "title-card";
});
</script>

<template>
  <component
    :is="tag"
    v-if="props.title"
    :class="[props.titleClass, props.titleColor, baseClass]"
  >
    {{ $t(props.title, props.title) }}
  </component>
</template>
