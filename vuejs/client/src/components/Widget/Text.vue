<script setup>
import Icons from "@components/Widget/Icons.vue";
import Flex from "@components/Widget/Flex.vue";

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
  @param {string} [textClass="text-content"] - Style of text. Can be replace by any class starting by 'text-' like 'text-stat'.
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
    default: "text-content",
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
</script>

<template>
  <component
    v-if="!props.icons"
    :is="props.tag"
    v-bind="props.attrs"
    :class="[props.textClass]"
  >
    {{ $t(props.text, props.text) }}
  </component>

  <Flex :flexClass="'justify-center'" v-if="props.icons">
    <Icons v-if="props.icons" v-bind="props.icons" />
    <component
      :is="props.tag"
      v-bind="props.attrs"
      :class="[props.textClass, 'ml-2']"
    >
      {{ $t(props.text, props.text) }}
    </component>
  </Flex>
</template>
