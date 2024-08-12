<script setup>
import { defineProps, reactive, onBeforeMount } from "vue";
import { useUUID } from "@utils/global.js";
/**
 *  @name Icons/Core.vue
 *  @description This component is a svg icon representing core plugin.
 *  @example
 *  {
 *    color: 'info',
 *  }
 *  @param {string} [iconClass="icon-default"] - The class of the icon.
 *  @param {any} [value=""] - Attach a value to icon. Useful on some cases like table filtering using icons.
 *  @param {string} [color="blue"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
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
    default: "blue",
  },
  disabled: { type: Boolean, required: false, default: false },
});

const icon = reactive({
  id: "",
  color: props.color || "blue",
});

onBeforeMount(() => {
  icon.id = useUUID();
});
</script>
<template>
  <span :id="icon.id" class="sr-only">{{ $t("icons_external_desc") }}</span>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    :data-color="icon.color"
    :data-value="props.value"
    :aria-disabled="props.disabled ? 'true' : 'false'"
    data-svg="external"
    role="img"
    :class="[props.iconClass, icon.color, 'fill']"
    :aria-labelledby="icon.id"
  >
    <path
      fill-rule="evenodd"
      d="M5.625 1.5H9a3.75 3.75 0 0 1 3.75 3.75v1.875c0 1.036.84 1.875 1.875 1.875H16.5a3.75 3.75 0 0 1 3.75 3.75v7.875c0 1.035-.84 1.875-1.875 1.875H5.625a1.875 1.875 0 0 1-1.875-1.875V3.375c0-1.036.84-1.875 1.875-1.875Zm5.845 17.03a.75.75 0 0 0 1.06 0l3-3a.75.75 0 1 0-1.06-1.06l-1.72 1.72V12a.75.75 0 0 0-1.5 0v4.19l-1.72-1.72a.75.75 0 0 0-1.06 1.06l3 3Z"
      clip-rule="evenodd"
    />
    <path
      d="M14.25 5.25a5.23 5.23 0 0 0-1.279-3.434 9.768 9.768 0 0 1 6.963 6.963A5.23 5.23 0 0 0 16.5 7.5h-1.875a.375.375 0 0 1-.375-.375V5.25Z"
    />
  </svg>
</template>
