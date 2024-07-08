<script setup>
import { reactive, defineProps } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import Fields from "@components/Form/Fields.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Container from "@components/Widget/Container.vue";

/** 
  @name Forms/Group/Multiple.vue
  @description This Will regroup all multiples settings with add and remove logic.
  This component under the hood is rendering default fields but by group with possibility to add or remove a multiple group.
  @example
  {
   "columns": {"pc": 6, "tablet": 12, "mobile": 12},
    "multiples": {
        "custom-headers": {
            "CUSTOM_HEADER": {
                "context": "multisite",
                "default": "",
                "help": "Custom header to add (HeaderName: HeaderValue).",
                "id": "custom-header",
                "label": "Custom header (HeaderName: HeaderValue)",
                "regex": "^([\\w\\-]+: .+)?$",
                "type": "text",
                "multiple": "custom-headers",
                "containerClass": "z-13",
                "pattern": "^([\\w\\-]+: .+)?$",
                "inpType": "input",
                "name": "Custom header (HeaderName: HeaderValue)",
                "columns": {
                    "pc": 4,
                    "tablet": 6,
                    "mobile": 12
                },
                "disabled": false,
                "value": "",
                "popovers": [
                    {
                        "iconName": "disk",
                        "text": "inp_popover_multisite"
                    },
                    {
                        "iconName": "info",
                        "text": "Custom header to add (HeaderName: HeaderValue)."
                    }
                ]
            }
        },
    },
    @param {object<object>} multiples - The multiples settings to display. This needs to be a dict of settings using default field format.
    @param {object} [columns={"pc": "12", "tablet": "12", "mobile": "12}] - Field has a grid system. This allow to get multiple field in the same row if needed.
    @param {string} [containerClass=""] - Additionnal class to add to the container
    @param {string} [tadId=contentIndex] - The tabindex of the field, by default it is the contentIndex
*/

const props = defineProps({
  // id && value && method
  multiples: {
    type: String,
    required: false,
    default: "",
  },
  columns: {
    type: [Object, Boolean],
    required: false,
    default: false,
  },
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  tabId: {
    type: [String, Number],
    required: false,
    default: contentIndex,
  },
});

const multiples = reactive({
  // Store value of multiple group
  // By default, all multiples are visible
  // But when clicking toggle, we can hide them by removing the key from the array
  visible: [],
});

const buttonAdd = {
  text: "action_add",
  color: "success",
  size: "normal",
  type: "button",
  containerClass: "flex justify-center",
};

const buttonToggle = {
  text: "action_toggle",
  color: "info",
  size: "normal",
  type: "button",
  containerClass: "flex justify-center",
};

function addGroup() {}
</script>

<template>
  <template v-for="(multObj, multName, id) in props.multiples">
    {{ id }}
    <Container
      data-is="multiple"
      class="layout-settings-multiple"
      :columns="props.columns"
      :containerClass="props.containerClass"
    >
      <Container class="col-span-12 flex items-center">
        <Subtitle :subtitle="multName.replaceAll('-', ' ')" />
        <ButtonGroup :buttons="[buttonAdd, buttonToggle]" />
      </Container>

      <Container class="layout-settings-multiple-group">
        <template v-for="(setting, value) in props.multiples[multName]">
          <Fields :setting="setting" :tabId="props.tabId" />
        </template>
      </Container>
    </Container>
  </template>
</template>
