<script setup>
/** 
  @name Content/Text.vue
  @description This component is used for regular paragraph.
    @example
  {
    text: "This is a paragraph",
    textClass: "text-3xl"
  }
  @param {string} text - The text value. Can be a translation key or by default raw text.
  @param {string} [textClass=""] - Additional class if needef
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
});
</script>

<template>
  <h5 :class="['content-text', props.textClass]">
    {{ $t(props.text, props.text) }}
  </h5>
</template>
