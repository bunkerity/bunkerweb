<script setup>
import { computed } from "vue";
/**
  @name Widget/Subtitle.vue
  @description This component is a general subtitle wrapper.
    @example
  {
    subtitle: "Total Users",
    type: "card",
    subtitleClass: "text-lg",
    subtitleColor : "info",
    tag: "h2"
  }
  @param {string} subtitle -  Can be a translation key or by default raw text.
  @param {string} type - The type of subtitle between "card", "container" or "stat"
  @param {string} [tag=""] - The tag of the subtitle. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of subtitle.
  @param {string} [subtitleColor=""] - The color of the subtitle between error, success, warning, info or tailwind color
  @param {string} [subtitleClass=""] - Additional class, useful when component is used directly on a grid system
*/

const props = defineProps({
  subtitle: {
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
  subtitleColor: {
    type: String,
    required: false,
    default: "",
  },
  subtitleClass: {
    type: String,
    required: false,
    default: "",
  },
});

const tag = computed(() => {
  if (props.tag) return props.tag;
  if (props.type === "container") return "p";
  if (props.type === "card") return "p";
  if (props.type === "stat") return "p";
});

const baseClass = computed(() => {
  if (props.type === "container") return "subtitle-container";
  if (props.type === "card") return "subtitle-card";
  if (props.type === "stat") return "subtitle-stat";
  return "subtitle-card";
});
</script>

<template>
  <component
    :is="tag"
    v-if="props.subtitle"
    :class="[props.subtitleClass, props.subtitleColor, baseClass]"
  >
    {{ $t(props.subtitle, props.subtitle) }}
  </component>
</template>
