<script setup>
/** 
  @name Widget/Text.vue
  @description This component is used for regular paragraph.
    @example
  {
    text: "This is a paragraph",
    textClass: "text-3xl"
  }
  @param {string} text - The text value. Can be a translation key or by default raw text.
  @param {string} [textClass="text-content"] - Style of text. Can be replace by any class starting by 'text-' like 'text-stat'.
  @param {string} [tag="p"] - The tag of the text. Can be p, span, div, h1, h2, h3, h4, h5, h6
*/

const props = defineProps({
  text: {
    type: [String, Number],
    required: true,
  },
  textClass: {
    type: String,
    required: false,
    default: "text-content",
  },
  tag: {
    type: String,
    required: false,
    default: "p",
  },
});
</script>

<template>
  <component :is="props.tag" :class="[props.textClass]">
    {{ $t(props.text, props.text) }}
  </component>
</template>
