<script setup>
import { useDisplayStore } from "@store/global.js";
import { defineProps, watch, reactive } from "vue";
/**
 *  @name Widget/Grid.vue
 *  @description This component is a basic container that can be used to wrap other components.
 *  This container is based on a grid system and will return a grid container with 12 columns.
 *  We can define additional class too.
 *  This component is mainly use as widget container or as a child of a GridLayout.
 *  @example
 *  {
 *    columns: { pc: 12, tablet: 12, mobile: 12},
 *    gridClass: "items-start"
 *  }
 *  @param {string} [gridClass="items-start"] - Additional class
 *  @param {array} [display=[]] - Array need to be of format ["groupName", "compId"] in order to be displayed using the display store. More info on the display store itslef.
 */

const props = defineProps({
  gridClass: {
    type: String,
    required: false,
    default: "items-start",
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
</script>

<template>
  <div
    v-if="container.isDisplay"
    data-grid
    :class="[props.gridClass, 'layout-grid']"
  >
    <slot></slot>
  </div>
</template>
