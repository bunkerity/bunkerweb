<script setup>
import Button from "@components/Widget/Button.vue";
import { onMounted, reactive, ref } from "vue";

/**
 *  @name Widget/ButtonGroup.vue
 *  @description This component allow to display multiple buttons in the same row using flex.
 *  We can define additional class too for the flex container.
 *  We need a list of buttons to display.
 *  @example
 *  {
 *    id: "group-btn",
 *    boutonGroupClass : "justify-center",
 *    buttons: [
 *      {
 *        id: "open-modal-btn",
 *        text: "Open modal",
 *        disabled: false,
 *        hideText: true,
 *        color: "green",
 *        size: "normal",
 *        iconName: "modal",
 *        eventAttr: {"store" : "modal", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"},
 *      },
 *      {
 *        id: "close-modal-btn",
 *        text: "Close modal",
 *        disabled: false,
 *        hideText: true,
 *        color: "red",
 *        size: "normal",
 *        iconName: "modal",
 *        eventAttr: {"store" : "modal", "value" : "close", "target" : "modal_id", "valueExpanded" : "close"},
 *      },
 *    ],
 *  }
 *  @param {Array} buttons - List of buttons to display. Button component is used.
 *  @param {String} [buttonGroupClass=""] - Additional class for the flex container
 */

const props = defineProps({
  buttons: {
    type: Array,
    required: true,
    default: [],
  },
  buttonGroupClass: {
    type: String,
    required: false,
    default: "",
  },
});

const group = reactive({
  class: "",
});

const groupEl = ref(null);

onMounted(() => {
  group.class =
    props.buttonGroupClass || groupEl?.value?.closest("[data-is]")
      ? `button-group-${groupEl.value
          .closest("[data-is]")
          .getAttribute("data-is")}`
      : "button-group-default";

  // Additional class for modal
  if (group.class.includes("modal")) {
    // Check if next sibling exists
    // Else, this is the last element, we can add a margin top because this is main modal action buttons
    if (!groupEl.value.nextElementSibling) {
      group.class += " last";
    }
  }
});
</script>

<template>
  <div
    ref="groupEl"
    :class="[group.class, props.buttonGroupClass]"
    v-if="props.buttons.length > 0"
  >
    <Button
      v-for="(button, id) in props.buttons"
      :key="button"
      v-bind="button.data"
      :class="[id === props.buttons.length - 1 ? '' : 'mr-2']"
    />
  </div>
</template>
