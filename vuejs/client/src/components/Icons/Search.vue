<script setup>
/** 
  @name Icons/Search.vue
  @description This component is a svg icon representing search.
  @example
  {
    iconColor: 'info',
  }
  @param {string} [iconClass="base"] - The class of the icon. "base" is the default size.
  @param {string} [iconColor="info"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
*/

const props = defineProps({
  iconClass: {
    type: String,
    required: false,
    default: "base",
  },
  iconColor: {
    type: String,
    required: false,
    default: "orange",
  },
});
</script>
<template>
  <svg
    data-svg="search"
    role="img"
    aria-hidden="true"
    :class="['icon-svg', props.iconClass, props.iconColor]"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    class="size-6"
  >
    <path d="M8.25 10.875a2.625 2.625 0 1 1 5.25 0 2.625 2.625 0 0 1-5.25 0Z" />
    <path
      fill-rule="evenodd"
      d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25Zm-1.125 4.5a4.125 4.125 0 1 0 2.338 7.524l2.007 2.006a.75.75 0 1 0 1.06-1.06l-2.006-2.007a4.125 4.125 0 0 0-3.399-6.463Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
