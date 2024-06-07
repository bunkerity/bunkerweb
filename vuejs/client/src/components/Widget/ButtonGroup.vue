<script setup>
import Flex from "@components/Widget/Flex.vue";
import Button from "@components/Widget/Button.vue";
import { v4 as uuidv4 } from "uuid";

/** 
  @name Widget/ButtonGroup.vue
  @description This component allow to display multiple buttons in the same row using flex.
  We can define additional class too for the flex container.
  We need a list of buttons to display.
  @example
  {
    id: "group-btn",
    groupClass : "justify-center",
    buttons: [
      {
        id: "open-modal-btn",
        text: "Open modal",
        disabled: false,
        hideText: true,
        color: "green",
        size: "normal",
        iconName: "modal",
        iconColor: "white",
        eventAttr: {"store" : "modal", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"},
      },
      {
        id: "close-modal-btn",
        text: "Close modal",
        disabled: false,
        hideText: true,
        color: "red",
        size: "normal",
        iconName: "modal",
        iconColor: "white",
        eventAttr: {"store" : "modal", "value" : "close", "target" : "modal_id", "valueExpanded" : "close"},
      },
    ],
  }
  @param {string} [id=uuidv4()] - Unique id of the button group
  @param {string} [groupClass="justify-center align-center"] - Additional class for the flex container
  @param {array} buttons - List of buttons to display. Button component is used.
*/

const props = defineProps({
  id: {
    type: String,
    required: false,
    default: uuidv4(),
  },
  groupClass: {
    type: String,
    required: false,
    default: "justify-center align-center",
  },
  buttons: {
    type: Array,
    required: true,
    default: [],
  },
});
</script>

<template>
  <Flex v-if="props.buttons.length > 0" :flexClass="props.groupClass">
    <Button
      v-for="(button, id) in props.buttons"
      :key="button"
      v-bind="button"
      :class="[id === props.buttons.length - 1 ? '' : 'mr-2']"
    />
  </Flex>
</template>
