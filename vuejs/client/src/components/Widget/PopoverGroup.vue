<script setup>
import Flex from "@components/Widget/Flex.vue";
import Popover from "@components/Widget/Popover.vue";
import { v4 as uuidv4 } from "uuid";

/** 
  @name Widget/PopoverGroup.vue
  @description This component allow to display multiple popovers in the same row using flex.
  We can define additional class too for the flex container.
  We need a list of popovers to display.
  @example
  {
    id: "group-popover",
    popoverClass : "justify-center",
    popovers: [
      {
        text: "This is a popover text",
        iconName: "info",
        iconColor: "info",
      },
      {
        text: "This is a popover text",
        iconName: "info",
        iconColor: "info",
      },
    ],
  }
  @param {string} [flexClass="justify-center align-center"] - Additional class for the flex container
  @param {array} popovers - List of popovers to display. Popover component is used.
*/

const props = defineProps({
  popovers: {
    type: Array,
    required: true,
    default: [],
  },
  flexClass: {
    type: String,
    required: false,
    default: "justify-center align-center",
  },
});
</script>

<template>
  <Flex v-if="props.popovers.length > 0" :flexClass="props.flexClass">
    <Popover
      v-for="(popover, id) in props.popovers"
      :key="popover"
      v-bind="popover"
      :popoverClass="id === props.popovers.length - 1 ? '' : 'mr-2'"
    />
  </Flex>
</template>
