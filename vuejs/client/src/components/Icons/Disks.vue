<script setup>
import { defineProps, reactive } from "vue";
/** 
  @name Icons/Disks.vue
  @description This component is a svg icon representing disks.
  @example
  {
    color: 'info',
  }
  @param {string} [iconClass="icon-default"] - The class of the icon.
   @param {string} [color="orange"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
*/

const props = defineProps({
  iconClass: {
    type: String,
    required: false,
    default: "icon-default",
  },
  color: {
    type: String,
    required: false,
    default: "orange",
  },
});

const icon = reactive({
  color: props.color || "orange",
});
</script>
<template>
  <svg
    :data-color="icon.color"
    data-svg="disks"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    role="img"
    aria-hidden="true"
    :class="[props.iconClass, icon.color, 'fill']"
  >
    <path
      d="M5.507 4.048A3 3 0 0 1 7.785 3h8.43a3 3 0 0 1 2.278 1.048l1.722 2.008A4.533 4.533 0 0 0 19.5 6h-15c-.243 0-.482.02-.715.056l1.722-2.008Z"
    />
    <path
      fill-rule="evenodd"
      d="M1.5 10.5a3 3 0 0 1 3-3h15a3 3 0 1 1 0 6h-15a3 3 0 0 1-3-3Zm15 0a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Zm2.25.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM4.5 15a3 3 0 1 0 0 6h15a3 3 0 1 0 0-6h-15Zm11.25 3.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM19.5 18a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
