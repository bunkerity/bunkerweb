<script setup>
import { useUUID } from "@utils/global.js";
import { defineProps, reactive, onMounted } from "vue";
/** 
  @name Icons/Check.vue
  @description This component is a svg icon representing a check mark.
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
    default: "success",
  },
});

const icon = reactive({
  id: "",
});

onMounted(() => {
  icon.id = useUUID(icon.id);
});
</script>
<template>
  <span :id="icon.id" class="sr-only">{{ $t("icons_check_desc") }}</span>
  <svg
    data-svg="check"
    role="img"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    :aria-labelledby="icon.id"
    :class="[props.iconClass, props.iconColor]"
  >
    <path
      fill-rule="evenodd"
      d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm13.36-1.814a.75.75 0 1 0-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 0 0-1.06 1.06l2.25 2.25a.75.75 0 0 0 1.14-.094l3.75-5.25Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
