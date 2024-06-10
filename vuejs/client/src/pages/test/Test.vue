<script setup>
import { reactive, onBeforeMount, triggerRef } from "vue";
import Checkbox from "@components/Forms/Field/Checkbox.vue";
import Select from "@components/Forms/Field/Select.vue";
import Input from "@components/Forms/Field/Input.vue";
import Datepicker from "@components/Forms/Field/Datepicker.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
import Button from "@components/Widget/Button.vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Grid from "@components/Widget/Grid.vue";

const checkboxData = {
  id: "test-checkbox",
  value: "yes",
  name: "test-checkbox",
  disabled: false,
  required: true,
  label: "Test checkbox",
  tabId: "1",
};

const selectData = {
  id: "test-select",
  value: "yes",
  values: ["yes", "no"],
  name: "test-select",
  disabled: false,
  required: false,
  requiredValues: ["no"],
  label: "Test select",
  tabId: "1",
  columns: { pc: 12, tablet: 12, mobile: 12 },
};

const inputData = {
  id: "test-input",
  value: "yes",
  type: "text",
  name: "test-input",
  disabled: false,
  required: true,
  label: "Test input",
  pattern: "(test)",
  tabId: "1",
  columns: { pc: 12, tablet: 12, mobile: 12 },
};

const datepickerData = {
  id: "test-datepicker",
  name: "test-datepicker",
  disabled: false,
  required: true,
  label: "Test datepicker",
  tabId: "1",
};

const buttonData = {
  id: "test-button",
  text: "Test button",
  type: "button",
  disabled: false,
  eventAttr: {
    store: "modal",
    default: "close",
    value: "open",
    target: "modal_id",
    valueExpanded: "open",
  },
  columns: { pc: 12, tablet: 12, mobile: 12 },
  tabId: "1",
};

const buttonSVGData = {
  id: "test-button",
  text: "Test button",
  type: "button",
  disabled: false,
  eventAttr: {
    store: "modal",
    default: "close",
    value: "open",
    target: "modal_id",
    valueExpanded: "open",
  },
  columns: { pc: 12, tablet: 12, mobile: 12 },
  tabId: "1",
  iconName: "plus",
};

const buttonOnlySVGData = {
  id: "test-button",
  text: "Test button",
  hideText: true,
  type: "button",
  disabled: false,
  eventAttr: {
    store: "modal",
    default: "close",
    value: "open",
    target: "modal_id",
    valueExpanded: "open",
  },
  columns: { pc: 12, tablet: 12, mobile: 12 },
  tabId: "1",
  iconName: "plus",
};

const comboboxData = {
  id: "test-combobox",
  value: "yes",
  values: ["yes", "no", "tes", "f", "fes", "esd", "fesfse"],
  name: "test-combobox",
  disabled: false,
  required: false,
  requiredValues: ["no"],
  label: "Test combobox",
  tabId: "1",
  columns: { pc: 12, tablet: 12, mobile: 12 },
};
</script>

<template>
  <DashboardLayout>
    <GridLayout :columns="{ pc: 4, tablet: 6, mobile: 12 }">
      <!-- widget grid -->
      <Grid>
        <Input v-bind="inputData" />
      </Grid>
    </GridLayout>
    <GridLayout :columns="{ pc: 4, tablet: 6, mobile: 12 }">
      <!-- widget grid -->
      <Grid>
        <Combobox v-bind="comboboxData" />
      </Grid>
    </GridLayout>
  </DashboardLayout>
</template>
