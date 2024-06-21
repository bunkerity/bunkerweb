<script setup>
/** 
  @name Icons/Carton.vue
  @description This component is a svg icon representing carton box.
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
    default: "info",
  },
});
</script>
<template>
  <svg
    data-svg="carton"
    role="img"
    aria-hidden="true"
    :class="['icon-svg', props.iconClass, props.iconColor]"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
  >
    <path
      d="M3.375 3C2.339 3 1.5 3.84 1.5 4.875v.75c0 1.036.84 1.875 1.875 1.875h17.25c1.035 0 1.875-.84 1.875-1.875v-.75C22.5 3.839 21.66 3 20.625 3H3.375Z"
    />
    <path
      fill-rule="evenodd"
      d="m3.087 9 .54 9.176A3 3 0 0 0 6.62 21h10.757a3 3 0 0 0 2.995-2.824L20.913 9H3.087Zm6.163 3.75A.75.75 0 0 1 10 12h4a.75.75 0 0 1 0 1.5h-4a.75.75 0 0 1-.75-.75Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
