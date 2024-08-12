<script setup>
import { defineProps, reactive } from "vue";
/**
 *  @name Icons/Search.vue
 *  @description This component is a svg icon representing search.
 *  @example
 *  {
 *    color: 'info',
 *  }
 *  @param {String} [iconClass="icon-default"] - The class of the icon.
 *  @param {Any} [value=""] - Attach a value to icon. Useful on some cases like table filtering using icons.
 *  @param {String} [color="info"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
 *  @param {Boolean} [disabled=false] - If true, the icon will be disabled.
 */

const props = defineProps({
  iconClass: {
    type: String,
    required: false,
    default: "icon-default",
  },
  value: {
    type: [String, Number],
    required: false,
    default: "",
  },
  color: {
    type: String,
    required: false,
    default: "info",
  },
  disabled: { type: Boolean, required: false, default: false },
});

const icon = reactive({
  color: props.color || "info",
});
</script>
<template>
  <svg
    :data-color="icon.color"
    :data-value="props.value"
    :aria-disabled="props.disabled ? 'true' : 'false'"
    data-svg="search"
    role="img"
    aria-hidden="true"
    :class="[props.iconClass, icon.color, 'fill']"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    class="size-6"
  >
    <path d="M8.25 10.875a2.625 2.625 0 1 1 5.25 0 2.625 2.625 0 0 1-5.25 0Z" />
    <path
      fill-rule="evenodd"
      d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25Zm-1.125 4.5a4.125 4.125 0 1 0 2.338 7.524l2.007 2.006a.75.75 0 1 0 1.06-1.06l-2.006-2.007a4.125 4.125 0 0 0-3.399-6.463Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
