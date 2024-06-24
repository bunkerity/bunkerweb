<script setup>
import { defineProps, reactive, onMounted } from "vue";
import { useUUID } from "@utils/global.js";
/** 
  @name Icons/Linkedin.vue
  @description This component is a svg icon representing Linkedin.
  @example
  {
    color: 'info',
  }
  @param {string} [iconClass="icon-default"] - The class of the icon.
  @param {string} [color="linkedin"]
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
    default: "linkedin",
  },
  disabled: { type: Boolean, required: false, default: false },
});

const icon = reactive({
  id: "",
  color: props.color || "linkedin",
});

onMounted(() => {
  icon.id = useUUID();
});
</script>
<template>
  <span :id="icon.id" class="sr-only">{{ $t("icons_linkedin_desc") }}</span>
  <svg
    :data-color="icon.color"
    :disabled="props.disabled"
    data-svg="key"
    role="img"
    :class="[props.iconClass, icon.color, 'fill']"
    fill="none"
    class="hover:opacity-80 dark:brightness-110"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 448 512"
    :aria-labelledby="icon.id"
  >
    <path
      d="M416 32H31.9C14.3 32 0 46.5 0 64.3v383.4C0 465.5 14.3 480 31.9 480H416c17.6 0 32-14.5 32-32.3V64.3c0-17.8-14.4-32.3-32-32.3zM135.4 416H69V202.2h66.5V416zm-33.2-243c-21.3 0-38.5-17.3-38.5-38.5S80.9 96 102.2 96c21.2 0 38.5 17.3 38.5 38.5 0 21.3-17.2 38.5-38.5 38.5zm282.1 243h-66.4V312c0-24.8-.5-56.7-34.5-56.7-34.6 0-39.9 27-39.9 54.9V416h-66.4V202.2h63.7v29.2h.9c8.9-16.8 30.6-34.5 62.9-34.5 67.2 0 79.7 44.3 79.7 101.9V416z"
    />
  </svg>
</template>
