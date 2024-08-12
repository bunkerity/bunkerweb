<script setup>
import { defineProps, reactive } from "vue";
/**
 *  @name Icons/Lock.vue
 *  @description This component is a svg icon representing lock.
 *  @example
 *  {
 *    color: 'info',
 *  }
 *  @param {String} [iconClass="icon-default"] - The class of the icon.
 *  @param {Any} [value=""] - Attach a value to icon. Useful on some cases like table filtering using icons.
 *  @param {String} [color="yellow"] - The color of the icon between some tailwind css available colors (purple, green, red, yellow, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
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
    default: "yellow",
  },
  disabled: { type: Boolean, required: false, default: false },
});

const icon = reactive({
  color: props.color || "yellow",
});
</script>
<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    :data-color="icon.color"
    :data-value="props.value"
    :aria-disabled="props.disabled ? 'true' : 'false'"
    data-svg="lock"
    role="img"
    aria-hidden="true"
    :class="[props.iconClass, icon.color, 'fill']"
  >
    <path
      fill-rule="evenodd"
      d="M12 1.5a5.25 5.25 0 0 0-5.25 5.25v3a3 3 0 0 0-3 3v6.75a3 3 0 0 0 3 3h10.5a3 3 0 0 0 3-3v-6.75a3 3 0 0 0-3-3v-3c0-2.9-2.35-5.25-5.25-5.25Zm3.75 8.25v-3a3.75 3.75 0 1 0-7.5 0v3h7.5Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
