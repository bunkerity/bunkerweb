<script setup>
import { computed } from 'vue';

/** 
  @name Widget/Flex.vue
  @description This component is a basic container that can be used to wrap other components.
  Per default, it aligns the components horizontally using flex.
  We can define additional class too.
  This component is mainly use as widget container or for groups of widget.
  @example
  {
  flexClass: "flex-start"
  }
  @param {string} [flexClass="flex-start"] - Additional class
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
