<script setup>
import { computed } from 'vue';

/* 
  This container component is mainly use as widget container.
  Each widget can define the base class for the container.
  In case we columns, this will use it too for positioning.

  PROPS ARGUMENTS
  *
  *
  class: string,
  columns: object,
  *
  *
*/

const props = defineProps({
  containerClass : {
    type: String,
    required: false,
    default : ""
  },
  columns: {
    type: [Object, Boolean],
    required: false,
    default: false
  },
})

const gridClass = computed(() => {
    return props.columns ? `col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}` : '';
})
</script>

<template>
  <div :class="[props.containerClass, gridClass]">
    <slot></slot>
  </div>
</template>