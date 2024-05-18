<script setup>
import { computed } from 'vue';

/** 
  @name Widget/Grid.vue
  @description This component is a basic container that can be used to wrap other components.
  This container is based on a grid system and will return a grid container with 12 columns.
  In case we are working with grid system, we can add columns to position the container.
  We can define additional class too.
  This component is mainly use as widget container or as a child of a GridLayout.
  @example
  {
    columns: { pc: 12, tablet: 12, mobile: 12},
    gridClass: "items-start"
  }
  @param {string} [gridClass="items-start"] - Additional class
  @param {object|boolean} [columns=false] - Work with grid system { pc: 12, tablet: 12, mobile: 12}
*/

const props = defineProps({
    columns : {
        type: [Object, Boolean],
        required: false,
        default : false,
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
