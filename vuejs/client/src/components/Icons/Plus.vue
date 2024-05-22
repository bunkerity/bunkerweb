<script setup>
/** 
  @name Icons/Plus.vue
  @description This component is a svg icon representing addition (+).
  @example
  {
    iconColor: 'info',
  }
  @param {string} [iconClass=""]
   @param {string} [iconColor="info"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
*/

const props = defineProps({
    iconClass : {
        type: String,
        required: false,
        default : "default-svg"
    },
    iconColor : {
        type: String,
        required: false,
        default: "info",
    }
})
</script>

<template>
    <svg  role="img"
    aria-hidden="true" 
    xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.5"
        stroke="currentColor"
        :class="[props.iconClass, props.iconColor]">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
</template>