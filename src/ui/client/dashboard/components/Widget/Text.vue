<script setup>
import Icons from "@components/Widget/Icons.vue";
import { onMounted, reactive, ref } from "vue";

/**
 *  @name Widget/Text.vue
 *  @description This component is used for regular paragraph.
 *  @example
 *  {
 *    text: "This is a paragraph",
 *    textClass: "text-3xl"
 *    attrs: { id: "paragraph" },
 *  }
 *  @param {String} text - The text value. Can be a translation key or by default raw text.
 *  @param {String} [textClass=""] - Style of text. Can be replace by any class starting by 'text-' like 'text-stat'.
 *  @param {String} [textIconContainerClass="col-span-12 flex justify-center items-center"] - Case we have icon with text, we wrap the text on a container with the icon. We can add a class to this container.
 *  @param {String} [color=""] - The color of the text between error, success, warning, info or tailwind color
 *  @param {String} [iconName=""] - The name of the icon to display before the text.
 *  @param {String} [iconColor=""] - The color of the icon.
 *  @param {Boolean} [bold=false] - If the text should be bold or not.
 *  @param {Boolean} [uppercase=false] - If the text should be uppercase or not.
 *  @param {String} [tag="p"] - The tag of the text. Can be p, span, div, h1, h2, h3, h4, h5, h6
 *  @param {Boolean|Object} [icon=false] - The icon to add before the text. If true, will add a default icon. If object, will add the icon with the name and the color.
 *  @param {Object} [attrs={}] - List of attributes to add to the text.
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
  textIconContainerClass: {
    type: String,
    required: false,
    default: "col-span-12 flex justify-center items-center",
  },
  color: {
    type: String,
    required: false,
    default: "",
  },
  bold: {
    type: Boolean,
    required: false,
    default: false,
  },
  uppercase: {
    type: Boolean,
    required: false,
    default: false,
  },
  tag: {
    type: String,
    required: false,
    default: "p",
  },
  iconName: {
    type: String,
    required: false,
    default: "",
  },
  iconColor: {
    type: String,
    required: false,
    default: "",
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
    props.textClass || renderEl.closest("[data-is]:not([data-is='text'])")
      ? `text-${renderEl
          .closest("[data-is]:not([data-is='text'])")
          .getAttribute("data-is")}`
      : "text-card";
});
</script>

<template>
  <component
    v-if="!props.iconName"
    :is="props.tag"
    v-bind="props.attrs"
    ref="textEl"
    :class="[
      text.class,
      props.color,
      'text-el',
      props.bold ? 'bold' : '',
      props.uppercase ? 'uppercase' : '',
    ]"
  >
    {{ $t(props.text, $t("dashboard_placeholder", props.text)) }}
  </component>

  <div
    :class="[props.textIconContainerClass]"
    v-if="props.iconName"
    data-is="text"
  >
    <Icons v-bind="{ iconName: props.iconName, color: props.iconColor }" />
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
