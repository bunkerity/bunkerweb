<script setup>
import { defineProps, reactive, onMounted } from "vue";
import { useUUID } from "@utils/global.js";
/** 
  @name Icons/Close.vue
  @description This component is a svg icon representing a close mark.
  @example
  {
    color: 'info',
  }
  @param {string} [iconClass="icon-default"] - The class of the icon.
   @param {string} [color="dark"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
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
    default: "dark",
  },
});

const icon = reactive({
  id: "",
  color: props.color || "dark",
});

onMounted(() => {
  icon.id = useUUID();
});
</script>
<template>
  <span :id="icon.id" class="sr-only">{{ $t("icons_cross_desc") }}</span>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    :data-color="icon.color"
    data-svg="cross"
    role="img"
    :class="[props.iconClass, icon.color, 'fill']"
    :aria-labelledby="icon.id"
  >
    <path
      fill-rule="evenodd"
      d="M5.47 5.47a.75.75 0 0 1 1.06 0L12 10.94l5.47-5.47a.75.75 0 1 1 1.06 1.06L13.06 12l5.47 5.47a.75.75 0 1 1-1.06 1.06L12 13.06l-5.47 5.47a.75.75 0 0 1-1.06-1.06L10.94 12 5.47 6.53a.75.75 0 0 1 0-1.06Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
