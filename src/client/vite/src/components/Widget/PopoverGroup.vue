<script setup>
import Popover from "@components/Widget/Popover.vue";

/** 
  @name Widget/PopoverGroup.vue
  @description This component allow to display multiple popovers in the same row using flex.
  We can define additional class too for the flex container.
  We need a list of popovers to display.
  @example
  {
    flexClass : "justify-center",
    popovers: [
      {
        text: "This is a popover text",
        iconName: "info",
      },
      {
        text: "This is a popover text",
        iconName: "info",
      },
    ],
  }
  @param {array} popovers - List of popovers to display. Popover component is used.
  @param {string} [groupClasss=""] - Additional class for the flex container
*/

const props = defineProps({
  popovers: {
    type: Array,
    required: true,
    default: [],
  },
  groupClasss: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <div
    v-if="props.popovers.length > 0"
    :class="['flex justify-center items-center', props.groupClasss]"
  >
    <Popover
      v-for="(popover, id) in props.popovers"
      :key="popover"
      v-bind="popover"
    />
  </div>
</template>
