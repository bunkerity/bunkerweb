<script setup>
import { v4 as uuidv4 } from "uuid";
import { defineProps, reactive } from "vue";
/** 
  @name Icons/Trespass.vue
  @description This component is a svg icon representing no trespassing.
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

const icon = reactive({
  id: uuidv4(),
});
</script>

<template>
  <span :id="icon.id" class="sr-only">{{ $t("icons_trespass_desc") }}</span>
  <svg
    data-svg="trespass"
    role="img"
    :aria-labelledby="icon.id"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    :class="[props.iconClass, props.iconColor]"
  >
    <path
      fill-rule="evenodd"
      d="m6.72 5.66 11.62 11.62A8.25 8.25 0 0 0 6.72 5.66Zm10.56 12.68L5.66 6.72a8.25 8.25 0 0 0 11.62 11.62ZM5.105 5.106c3.807-3.808 9.98-3.808 13.788 0 3.808 3.807 3.808 9.98 0 13.788-3.807 3.808-9.98 3.808-13.788 0-3.808-3.807-3.808-9.98 0-13.788Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
