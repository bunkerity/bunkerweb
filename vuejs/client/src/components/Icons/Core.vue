<script setup>
import { defineProps, reactive, onMounted } from "vue";
import { useUUID } from "@utils/global.js";
/** 
  @name Icons/Core.vue
  @description This component is a svg icon representing core plugin.
  @example
  {
    color: 'info',
  }
  @param {string} [iconClass="icon-default"] - The class of the icon.
   @param {string} [color="cyan-darker"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
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
    default: "cyan-darker",
  },
});

const icon = reactive({
  id: "",
  color: props.color || "cyan-darker",
});

onMounted(() => {
  icon.id = useUUID();
});
</script>
<template>
  <span :id="icon.id" class="sr-only">{{ $t("icons_core_desc") }}</span>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    :data-color="icon.color"
    data-svg="core"
    role="img"
    :class="[props.iconClass, icon.color, 'fill']"
    :aria-labelledby="icon.id"
  >
    <path d="M16.5 7.5h-9v9h9v-9Z" />
    <path
      fill-rule="evenodd"
      d="M8.25 2.25A.75.75 0 0 1 9 3v.75h2.25V3a.75.75 0 0 1 1.5 0v.75H15V3a.75.75 0 0 1 1.5 0v.75h.75a3 3 0 0 1 3 3v.75H21A.75.75 0 0 1 21 9h-.75v2.25H21a.75.75 0 0 1 0 1.5h-.75V15H21a.75.75 0 0 1 0 1.5h-.75v.75a3 3 0 0 1-3 3h-.75V21a.75.75 0 0 1-1.5 0v-.75h-2.25V21a.75.75 0 0 1-1.5 0v-.75H9V21a.75.75 0 0 1-1.5 0v-.75h-.75a3 3 0 0 1-3-3v-.75H3A.75.75 0 0 1 3 15h.75v-2.25H3a.75.75 0 0 1 0-1.5h.75V9H3a.75.75 0 0 1 0-1.5h.75v-.75a3 3 0 0 1 3-3h.75V3a.75.75 0 0 1 .75-.75ZM6 6.75A.75.75 0 0 1 6.75 6h10.5a.75.75 0 0 1 .75.75v10.5a.75.75 0 0 1-.75.75H6.75a.75.75 0 0 1-.75-.75V6.75Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
