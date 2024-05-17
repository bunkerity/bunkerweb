<script setup>
import { computed } from 'vue';

/* 
  This container component is used to align groups of components horizontally using flex.

  PROPS ARGUMENTS
  *
  *
  class: string,
  horizontalAlign: string<"flex-start"|"center"|"flex-end"|"space-between"|"space-around"|"space-evenly">,
  *
  *
*/

const props = defineProps({
    class: {
        type: String,
        required: false,
        default : "flex-start"
    },
})

const flexClass = computed(() => {
    return `w-full flex ${props.class}`;
})

</script>

<template>
<div :class="[flexClass]">
    <slot></slot>
</div>
</template>
