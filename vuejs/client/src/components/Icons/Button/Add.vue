<script setup>
import { computed } from 'vue';


/* 
  COMPONENT DESCRIPTION
  *
  *
  This svg component is used to create a complete svg icon for a button.
  *
  *
  PROPS ARGUMENTS
  *
  *
  iconColor: string,
  *
  *
  PROPS EXAMPLE
  *
  *
  iconColor: 'white',
  *
  *
*/

const props = defineProps({
    iconColor : {
        type: String,
        required: false,
        default: "white",
    }
})

const svgClass = computed(() => {
    return `w-6.5 h-6.5 ${props.iconColor}`
})
</script>

<template>
    <svg xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.5"
        stroke="currentColor"
        :class="[svgClass]">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
</template>