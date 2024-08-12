<script setup>
import { defineProps, reactive } from "vue";
/**
 *  @name Icons/Disk.vue
 *  @description This component is a svg icon representing disk.
 *  @example
 *  {
 *    color: 'info',
 *  }
 *  @param {String} [iconClass="icon-default"] - The class of the icon.
 *  @param {Any} [value=""] - Attach a value to icon. Useful on some cases like table filtering using icons.
 *  @param {String} [color="orange"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
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
    default: "orange",
  },
  disabled: { type: Boolean, required: false, default: false },
});

const icon = reactive({
  color: props.color || "orange",
});
</script>
<template>
  <svg
    :data-color="icon.color"
    :data-value="props.value"
    :aria-disabled="props.disabled ? 'true' : 'false'"
    data-svg="disk"
    role="img"
    aria-hidden="true"
    :class="[props.iconClass, icon.color, 'fill']"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
  >
    <path
      d="M4.08 5.227A3 3 0 0 1 6.979 3H17.02a3 3 0 0 1 2.9 2.227l2.113 7.926A5.228 5.228 0 0 0 18.75 12H5.25a5.228 5.228 0 0 0-3.284 1.153L4.08 5.227Z"
    />
    <path
      fill-rule="evenodd"
      d="M5.25 13.5a3.75 3.75 0 1 0 0 7.5h13.5a3.75 3.75 0 1 0 0-7.5H5.25Zm10.5 4.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm3.75-.75a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
