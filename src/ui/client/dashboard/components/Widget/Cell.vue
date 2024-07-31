<script setup>
import { reactive, computed, ref, onMounted, watch } from "vue";
import Text from "@components/Widget/Text.vue";
import Icons from "@components/Widget/Icons.vue";
import Fields from "@components/Form/Fields.vue";
import Button from "@components/Widget/Button.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import { useEqualStr } from "@utils/global.js";

/**
  @name Builder/Cell.vue
  @description This component includes all elements that can be shown in a table cell.
  @example
   { type : "button",
     data : {
       id: "open-modal-btn",
       text: "Open modal",
       disabled: false,
       hideText: true,
       color: "green",
       size: "normal",
       iconName: "modal",
       attrs: { data-toggle: "modal", "data-target": "#modal"},
     }
  }
  @param {string} type - The type of the cell. This needs to be a Vue component.
  @param {object} data - The data to display in the cell. This needs to be the props of the Vue component.
*/

const props = defineProps({
  type: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
});
</script>

<template>
  <Text v-if="useEqualStr(props.type, 'Text')" v-bind="props.data" />
  <Icons v-if="useEqualStr(props.type, 'Icons')" v-bind="props.data" />
  <Fields v-if="useEqualStr(props.type, 'Fields')" v-bind="props.data" />
  <Button v-if="useEqualStr(props.type, 'Button')" v-bind="props.data" />
  <ButtonGroup
    v-if="useEqualStr(props.type, 'ButtonGroup')"
    v-bind="props.data"
  />
</template>
