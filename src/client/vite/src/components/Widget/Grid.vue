<script setup>
/** 
  @name Widget/Grid.vue
  @description This component is a basic container that can be used to wrap other components.
  This container is based on a grid system and will return a grid container with 12 columns.
  We can define additional class too.
  This component is mainly use as widget container or as a child of a GridLayout.
  @example
  {
    columns: { pc: 12, tablet: 12, mobile: 12},
    gridClass: "items-start"
  }
  @param {string} [gridClass="items-start"] - Additional class
*/

const props = defineProps({
  gridClass: {
    type: String,
    required: false,
    default: "items-start",
  },
});
</script>

<template>
  <div data-grid :class="[props.gridClass, 'layout-grid']">
    <slot></slot>
  </div>
</template>
