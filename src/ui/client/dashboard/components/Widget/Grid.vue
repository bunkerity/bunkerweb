<script setup>
import { useDisplayStore } from "@store/global.js";
import { defineProps, watch, reactive, onMounted } from "vue";
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
 *  @param {String} [gridClass="items-start"] - Additional class
 *  @param {Array} [display=[]] - Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef.
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

/**
 *  @name checkDisplay
 *  @description Check if the current display value is matching the display store value.
 *  @returns {Void}
 */
function checkDisplay() {
  if (!props.display.length) return;
  container.isDisplay = displayStore.isCurrentDisplay(
    props.display[0],
    props.display[1]
  );
}

// Case we have set a display group name and component id, the component id must match the current display id for the same group name to be displayed.
if (props.display.length) {
  watch(displayStore.display, (val) => {
    checkDisplay();
  });
}
</script>

<template>
  <div
    v-show="container.isDisplay"
    :aria-hidden="container.isDisplay ? 'false' : 'true'"
    data-grid
    :class="[props.gridClass, 'layout-grid']"
  >
    <slot></slot>
  </div>
</template>
