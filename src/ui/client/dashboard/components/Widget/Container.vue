<script setup>
import { useDisplayStore } from "@store/global.js";
import { defineProps, watch, computed, reactive } from "vue";
/**
 *  @name Widget/Container.vue
 *  @description This component is a basic container that can be used to wrap other components.
 *  In case we are working with grid system, we can add columns to position the container.
 *  We can define additional class too.
 *  This component is mainly use as widget container.
 *  @example
 *  {
 *    containerClass: "w-full h-full bg-white rounded shadow-md",
 *    columns: { pc: 12, tablet: 12, mobile: 12}
 *  }
 *  @param {string} [containerClass=""] - Additional class
 *  @param {object|boolean} [columns=false] - Work with grid system { pc: 12, tablet: 12, mobile: 12}
 *  @param {string} [tag="div"] - The tag for the container
 *  @param {array} [display=[]] - Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef.
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
  tag: {
    type: String,
    required: false,
    default: "div",
  },
  display: {
    type: Array,
    required: false,
    default: [],
  },
});

const displayStore = useDisplayStore();

const container = reactive({
  // Check if component display is related to the displayStore
  isDisplay: props.display.length
    ? displayStore.isCurrentDisplay(props.display[0], props.display[1])
    : true,
});

// Case we have set a display group name and component id, the component id must match the current display id for the same group name to be displayed.
if (props.display.length) {
  watch(displayStore.display, (val) => {
    container.isDisplay = displayStore.isCurrentDisplay(
      props.display[0],
      props.display[1]
    );
  });
}

const gridClass = computed(() => {
  return props.columns
    ? `col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}`
    : "";
});
</script>

<template>
  <component
    v-if="container.isDisplay"
    :is="props.tag"
    data-container
    :class="[props.containerClass ? props.containerClass : '', gridClass]"
  >
    <slot></slot>
  </component>
</template>
