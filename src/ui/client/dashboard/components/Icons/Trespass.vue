<script setup>
import { defineProps, reactive, onBeforeMount } from "vue";
import { useUUID } from "@utils/global.js";
/**
  @name Icons/Trespass.vue
  @description This component is a svg icon representing no trespassing.
  @example
  {
    color: 'info',
  }
  @param {string} [iconClass="icon-default"] - The class of the icon.
   @param {string} [color="error"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
  @param {boolean} [disabled=false] - If true, the icon will be disabled.
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
    default: "error",
  },
  disabled: { type: Boolean, required: false, default: false },
});

const icon = reactive({
  id: "",
  color: props.color || "error",
});

onBeforeMount(() => {
  icon.id = useUUID();
});
</script>

<template>
  <span :id="icon.id" class="sr-only">{{ $t("icons_trespass_desc") }}</span>
  <svg
    :data-color="icon.color"
    :aria-disabled="props.disabled ? 'true' : 'false'"
    data-svg="trespass"
    role="img"
    :aria-labelledby="icon.id"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    :class="[props.iconClass, icon.color, 'fill']"
  >
    <path
      fill-rule="evenodd"
      d="m6.72 5.66 11.62 11.62A8.25 8.25 0 0 0 6.72 5.66Zm10.56 12.68L5.66 6.72a8.25 8.25 0 0 0 11.62 11.62ZM5.105 5.106c3.807-3.808 9.98-3.808 13.788 0 3.808 3.807 3.808 9.98 0 13.788-3.807 3.808-9.98 3.808-13.788 0-3.808-3.807-3.808-9.98 0-13.788Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
