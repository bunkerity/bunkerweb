<script setup>
import Icons from "@components/Widget/Icons.vue";
import Flex from "@components/Widget/Flex.vue";
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
  @param {boolean|object} [icons=false] - The popover to display with the text. Check Popover component for more details.
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
  icons: {
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
  text.class =
    props.textClass || (textEl.value && textEl.value.closest("[data-is]"))
      ? `text-${textEl.value.closest("[data-is]").getAttribute("data-is")}`
      : textIconEl.value && textIconEl.value.closest("[data-is]")
      ? `text-${textIconEl.value.closest("[data-is]").getAttribute("data-is")}`
      : "text-content";
});
</script>

<template>
  <component
    v-if="!props.icons"
    :is="props.tag"
    v-bind="props.attrs"
    ref="textEl"
    :class="[text.class, props.color]"
  >
    {{ $t(props.text, props.text) }}
  </component>

  <Flex :flexClass="'justify-center'" v-if="props.icons">
    <Icons v-if="props.icons" v-bind="props.icons" />
    <component
      ref="textIconEl"
      :is="props.tag"
      v-bind="props.attrs"
      :class="[text.class, props.color, 'ml-2']"
    >
      {{ $t(props.text, props.text) }}
    </component>
  </Flex>
</template>
