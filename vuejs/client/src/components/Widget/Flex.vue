<script setup>
import { computed } from 'vue';

/*
  COMPONENT DESCRIPTION
  *
  *
  This container component is used to align groups of components horizontally using flex.
  *
  *
  PROPS ARGUMENTS
  *
  *
  flexClass: string,
  *
  *
  PROPS EXAMPLE
  *
  *
  flexClass: "flex-start"
  *
  *
*/

const props = defineProps({
    flexClass: {
        type: String,
        required: false,
        default : "flex-start"
    },
})

const flexClass = computed(() => {
    return `w-full flex ${props.flexClass}`;
})

</script>

<template>
<div :class="[flexClass]">
    <slot></slot>
</div>
</template>
