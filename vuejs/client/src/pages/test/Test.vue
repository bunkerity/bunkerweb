<script setup>
import { reactive, onBeforeMount, triggerRef } from "vue";
import Checkbox from "@components/Forms/Field/Checkbox.vue";
import Select from "@components/Forms/Field/Select.vue";
import Input from "@components/Forms/Field/Input.vue";
import Datepicker from "@components/Forms/Field/Datepicker.vue";
import Button from "@components/Widget/Button.vue";


const checkboxData = {
  id: 'test-checkbox',
  value: 'yes',
  name: 'test-checkbox',
  disabled: false,
  required: true,
  label: 'Test checkbox',
  tabId: '1',

}

const selectData = {
  id: 'test-select',
  value: 'yes',
  values: ['yes', 'no'],
  name: 'test-select',
  disabled: false,
  required: false,
  requiredValues : ["no"],
  label: 'Test select',
  tabId: '1',
}

const inputData = {
  id: 'test-input',
  value: 'yes',
  type: "text",
  name: 'test-input',
  disabled: false,
  required: true,
  label: 'Test input',
  pattern : "(test)",
  tabId: '1',
}

const datepickerData = {
  id: 'test-datepicker',
  name: 'test-datepicker',
  disabled: false,
  required: true,
  label: 'Test datepicker',
  tabId: '1',
}

const buttonData = {
  id: 'test-button',
  text: 'Test button',
  type: 'button',
  disabled: false,
  eventAttr: {"store" : "modal", "default" : "close", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"},
  columns: {"pc": 12, "tablet": 12, "mobile": 12},
  tabId: '1',
}

const buttonSVGData = {
  id: 'test-button',
  text: 'Test button',
  type: 'button',
  disabled: false,
  eventAttr: {"store" : "modal", "default" : "close", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"},
  columns: {"pc": 12, "tablet": 12, "mobile": 12},
  tabId: '1',
  iconName : "add"
}

const buttonOnlySVGData = {
  id: 'test-button',
  text: 'Test button',
  hideText : true,
  type: 'button',
  disabled: false,
  eventAttr: {"store" : "modal", "default" : "close", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"},
  columns: {"pc": 12, "tablet": 12, "mobile": 12},
  tabId: '1',
  iconName : "add"
}
</script>

<template>
    <div class="bg-secondary flex flex-col items-center justify-center h-full">
      <div style="width: 300px;">
        <Checkbox v-bind="checkboxData" />
        <Select v-bind="selectData" />
        <Input v-bind="inputData" />
        <Datepicker v-bind="datepickerData" />
        <Button v-bind="buttonData" />
        <Button v-bind="buttonSVGData" />
        <Button v-bind="buttonOnlySVGData" />
      </div>
    </div>
</template>
