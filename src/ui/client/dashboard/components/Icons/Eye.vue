<script setup>
import { defineProps, reactive } from "vue";
/**
 *  @name Icons/Eye.vue
 *  @description This component is a svg icon representing eye.
 *  @example
 *  {
 *    color: 'green',
 *  }
 *  @param {string} [iconClass="icon-default"] - The class of the icon.
 *  @param {any} [value=""] - Attach a value to icon. Useful on some cases like table filtering using icons.
 *  @param {string} [color="cyan"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
 *  @param {boolean} [disabled=false] - If true, the icon will be disabled.
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
    default: "green",
  },
  disabled: { type: Boolean, required: false, default: false },
});

const icon = reactive({
  color: props.color || "green",
});
</script>
<template>
  <svg
    :data-color="icon.color"
    :data-value="props.value"
    :aria-disabled="props.disabled ? 'true' : 'false'"
    data-svg="document"
    role="img"
    aria-hidden="true"
    :class="[props.iconClass, icon.color, 'fill']"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
  >
    <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
    <path
      fill-rule="evenodd"
      d="M1.323 11.447C2.811 6.976 7.028 3.75 12.001 3.75c4.97 0 9.185 3.223 10.675 7.69.12.362.12.752 0 1.113-1.487 4.471-5.705 7.697-10.677 7.697-4.97 0-9.186-3.223-10.675-7.69a1.762 1.762 0 0 1 0-1.113ZM17.25 12a5.25 5.25 0 1 1-10.5 0 5.25 5.25 0 0 1 10.5 0Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
