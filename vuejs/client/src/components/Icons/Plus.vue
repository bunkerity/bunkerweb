<script setup>
import { defineProps, reactive, onMounted } from "vue";
import { useUUID } from "@utils/global.js";
/** 
  @name Icons/Plus.vue
  @description This component is a svg icon representing addition (+).
  @example
  {
    color: 'info',
  }
  @param {string} [iconClass="icon-default"] - The class of the icon.
   @param {string} [color="success"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
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
    default: "success",
  },
  disabled: { type: Boolean, required: false, default: false },
});

const icon = reactive({
  id: "",
  color: props.color || "success",
});

onMounted(() => {
  icon.id = useUUID();
});
</script>

<template>
  <span :id="icon.id" class="sr-only">{{ $t("icons_plus_desc") }}</span>
  <svg
    :data-color="icon.color"
    :aria-disabled="props.disabled ? 'true' : 'false'"
    data-svg="plus"
    role="img"
    :aria-labelledby="icon.id"
    :class="[props.iconClass, icon.color, 'fill']"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
  >
    <path
      fill-rule="evenodd"
      d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25ZM12.75 9a.75.75 0 0 0-1.5 0v2.25H9a.75.75 0 0 0 0 1.5h2.25V15a.75.75 0 0 0 1.5 0v-2.25H15a.75.75 0 0 0 0-1.5h-2.25V9Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
