<script setup>
import { defineProps, reactive } from "vue";
/**
 *  @name Icons/Uncheck.vue
 *  @description This component is a svg icon representing uncheck.
 *  @example
 *  {
 *    color: 'info',
 *  }
 *  @param {String} [iconClass="icon-default"] - The class of the icon.
 *  @param {Any} [value=""] - Attach a value to icon. Useful on some cases like table filtering using icons.
 *  @param {String} [color="dark"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
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
    default: "dark",
  },
  disabled: { type: Boolean, required: false, default: false },
});

const icon = reactive({
  color: props.color || "dark",
});
</script>
<template>
  <svg
    :data-color="icon.color"
    :data-value="props.value"
    :aria-disabled="props.disabled ? 'true' : 'false'"
    data-svg="uncheck"
    role="img"
    aria-hidden="true"
    :class="[props.iconClass, icon.color, 'fill dark:brightness-[125%]']"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
  >
    <path
      fill-rule="evenodd"
      d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25Zm3 10.5a.75.75 0 0 0 0-1.5H9a.75.75 0 0 0 0 1.5h6Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
