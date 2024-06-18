<script setup>
import { v4 as uuidv4 } from "uuid";

/** 
  @name Icons/Core.vue
  @description This component is a svg icon representing core plugin.
  @example
  {
    iconColor: 'info',
  }
  @param {string} [iconClass=""]
   @param {string} [iconColor="info"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
*/

const props = defineProps({
  iconClass: {
    type: String,
    required: false,
    default: "default-svg",
  },
  iconColor: {
    type: String,
    required: false,
    default: "info",
  },
});

const id = uuidv4();
</script>
<template>
  <svg
    data-svg="core"
    role="img"
    :class="[props.iconClass, props.iconColor]"
    :aria-labelledby="id"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 384 512"
  >
    <span :id="id" class="sr-only">{{ $t("icons_core_desc") }}</span>
    <path
      d="M0 64C0 28.7 28.7 0 64 0H224V128c0 17.7 14.3 32 32 32H384V448c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V64zm384 64H256V0L384 128z"
    />
  </svg>
</template>
