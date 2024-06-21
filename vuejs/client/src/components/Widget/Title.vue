<script setup>
import { computed, onMounted, reactive, ref } from "vue";
/**
  @name Widget/Title.vue
  @description This component is a general title wrapper.
    @example
  {
    title: "Total Users",
    type: "card",
    titleClass: "text-lg",
    color : "info",
    tag: "h2"
  }
  @param {string} title -  Can be a translation key or by default raw text.
  @param {string} [type="card"] - The type of title between "container", "card", "content", "min" or "stat"
  @param {string} [tag=""] - The tag of the title. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of title.
  @param {string} [color=""] - The color of the title between error, success, warning, info or tailwind color
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
  color: {
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

const title = reactive({
  isSubtitle: false,
  class: "",
});

const titleEl = ref(null);

const tag = computed(() => {
  if (props.tag) return props.tag;
  if (props.type === "container") return "h1";
  if (props.type === "card") return "h2";
  return "p";
});

// Add or remove margin bottom
const isSubtitleClass = computed(() => {
  return title.isSubtitle ? "is-subtitle" : "no-subtitle";
});

onMounted(() => {
  // Check if next sibling is a subtitle
  const nextSibling = titleEl.value.nextElementSibling;
  title.isSubtitle =
    !nextSibling || !nextSibling.hasAttribute("data-subtitle") ? false : true;

  title.class =
    props.titleClass || titleEl.value.closest("[data-is]")
      ? `title-${titleEl.value.closest("[data-is]").getAttribute("data-is")}`
      : "title-card";
});
</script>

<template>
  <component
    ref="titleEl"
    data-title
    :is="tag"
    v-if="props.title"
    :class="[props.color, isSubtitleClass, title.class]"
  >
    {{ $t(props.title, props.title) }}
  </component>
</template>
