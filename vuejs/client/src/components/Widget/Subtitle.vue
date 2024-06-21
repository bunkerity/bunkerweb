<script setup>
import { computed, onMounted, reactive, ref } from "vue";
/**
  @name Widget/Subtitle.vue
  @description This component is a general subtitle wrapper.
    @example
  {
    subtitle: "Total Users",
    type: "card",
    subtitleClass: "text-lg",
    color : "info",
    tag: "h2"
  }
  @param {string} subtitle -  Can be a translation key or by default raw text.
  @param {string} [type="card"] - The type of title between "container", "card", "content", "min" or "stat"
  @param {string} [tag=""] - The tag of the subtitle. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of subtitle.
  @param {string} [color=""] - The color of the subtitle between error, success, warning, info or tailwind color
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
  color: {
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
  return "p";
});

const subtitle = reactive({
  class: "",
});

const subtitleEl = ref(null);

onMounted(() => {
  subtitle.class =
    props.subtitleClass || subtitleEl.value.closest("[data-is]")
      ? `subtitle-${subtitleEl.value
          .closest("[data-is]")
          .getAttribute("data-is")}`
      : "subtitle-card";
});
</script>

<template>
  <component
    ref="subtitleEl"
    data-subtitle
    :is="tag"
    v-if="props.subtitle"
    :class="[subtitle.class, props.color]"
  >
    {{ $t(props.subtitle, props.subtitle) }}
  </component>
</template>
