<script setup>
import Icons from "@components/Widget/Icons.vue";
import { onMounted, reactive, ref } from "vue";

/**
  @name Widget/Text.vue
  @description This component is used for regular paragraph.
    @example
  {
    text: "This is a paragraph",
    textClass: "text-3xl"
    attrs: { id: "paragraph" },
  }
  @param {string} text - The text value. Can be a translation key or by default raw text.
  @param {string} [textClass=""] - Style of text. Can be replace by any class starting by 'text-' like 'text-stat'.
  @param {string} [color=""] - The color of the text between error, success, warning, info or tailwind color
  @param {string} [tag="p"] - The tag of the text. Can be p, span, div, h1, h2, h3, h4, h5, h6
  @param {boolean|object} [icon=false] - The icon to add before the text. If true, will add a default icon. If object, will add the icon with the name and the color.
  @param {object} [attrs={}] - List of attributs to add to the text.
*/

const props = defineProps({
  text: {
    type: [String, Number],
    required: true,
  },
  textClass: {
    type: String,
    required: false,
    default: "",
  },
  color: {
    type: String,
    required: false,
    default: "",
  },
  tag: {
    type: String,
    required: false,
    default: "p",
  },
  icon: {
    type: [Boolean, Object],
    required: false,
    default: false,
  },
  attrs: {
    type: Object,
    required: false,
    default: {},
  },
});

// Add or remove margin bottom
const text = reactive({
  class: "",
});

const textEl = ref(null);
const textIconEl = ref(null);

onMounted(() => {
  // Check if next sibling is a
  const renderEl = textEl.value || textIconEl.value || null;

  text.class =
    props.textClass || renderEl.closest("[data-is]")
      ? `text-${renderEl.closest("[data-is]").getAttribute("data-is")}`
      : "text-card";
});
</script>

<template>
  <component
    v-if="!props.icon"
    :is="props.tag"
    v-bind="props.attrs"
    ref="textEl"
    :class="[text.class, props.color, 'text-el']"
  >
    {{ $t(props.text, $t("dashboard_placeholder", props.text)) }}
  </component>

  <div :class="['flex justify-center items-center']" v-if="props.icon">
    <Icons v-if="props.icon" v-bind="props.icon" />
    <component
      ref="textIconEl"
      :is="props.tag"
      v-bind="props.attrs"
      :class="[text.class, props.color, 'text-el', 'ml-2']"
    >
      {{ $t(props.text, $t("dashboard_placeholder", props.text)) }}
    </component>
  </div>
</template>
