<script setup>
import { computed } from "vue";

/** 
  @name Widget/Container.vue
  @description This component is a basic container that can be used to wrap other components.
  In case we are working with grid system, we can add columns to position the container.
  We can define additional class too.
  This component is mainly use as widget container.
  @example
  {
    containerClass: "w-full h-full bg-white rounded shadow-md",
    columns: { pc: 12, tablet: 12, mobile: 12}
  }
  @param {string} [containerClass=""] - Additional class
  @param {object|boolean} [columns=false] - Work with grid system { pc: 12, tablet: 12, mobile: 12}
*/

const props = defineProps({
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  columns: {
    type: [Object, Boolean],
    required: false,
    default: false,
  },
});

const gridClass = computed(() => {
  return props.columns
    ? `col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}`
    : "";
});
</script>

<template>
  <div
    data-container
    :class="[props.containerClass ? props.containerClass : '', gridClass]"
  >
    <slot></slot>
  </div>
</template>
