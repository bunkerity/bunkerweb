<script setup>
/** 
  @name Icons/Lock.vue
  @description This component is a svg icon representing lock.
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
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    data-svg="lock"
    role="img"
    aria-hidden="true"
    :class="['icon-svg', props.iconClass, props.iconColor]"
  >
    <path
      fill-rule="evenodd"
      d="M12 1.5a5.25 5.25 0 0 0-5.25 5.25v3a3 3 0 0 0-3 3v6.75a3 3 0 0 0 3 3h10.5a3 3 0 0 0 3-3v-6.75a3 3 0 0 0-3-3v-3c0-2.9-2.35-5.25-5.25-5.25Zm3.75 8.25v-3a3.75 3.75 0 1 0-7.5 0v3h7.5Z"
      clip-rule="evenodd"
    />
  </svg>
</template>
