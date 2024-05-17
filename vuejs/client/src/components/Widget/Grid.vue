<script setup>
import { computed } from 'vue';

/* 
  COMPONENT DESCRIPTION
  *
  *
  This Grid component is a container with a grid system.
  In case we are adding columns, this will be added, so it can be used with parent grid.
  *
  *
  PROPS ARGUMENTS
  *
  *
  type : <"card"|"table"|...>  (will determine component style)
  title: string,
  columns : { pc: int, tablet: int, mobile: int},
  class : <"items-start"|"items-center"|"items-end">
  *
  *
  PROPS EXAMPLE
  *
  *
  columns: { pc: 12, tablet: 12, mobile: 12},
  gridClass: "items-start"
  *
  *
*/

const props = defineProps({
    columns : {
        type: [Object, Boolean],
        required: false,
        default : {
            pc: 12,
            tablet: 12,
            mobile: 12}
    },
gridClass : {
        type: String,
        required: false,
        default: "items-start"
    },
})


const gridClass = computed(() => {
    return `grid grid-cols-12 w-full ${props.gridClass}`;
})

const columnClass = computed(() => {
    return props.columns ? `col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}` : ``;
})

</script>

<template>
<div :class="[gridClass, columnClass]">
    <slot></slot>
</div>
</template>
