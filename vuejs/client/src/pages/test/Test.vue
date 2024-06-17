<script setup>
import { reactive, onBeforeMount, triggerRef } from "vue";
import Input from "@components/Forms/Field/Input.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
import Editor from "@components/Forms/Field/Editor.vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Grid from "@components/Widget/Grid.vue";
import Table from "@components/Widget/Table.vue";

const inputData = {
  id: "test-input",
  value: "yes",
  type: "password",
  name: "test-input",
  disabled: false,
  required: true,
  label: "Test input",
  pattern: "(test)",
  columns: { pc: 12, tablet: 12, mobile: 12 },
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
  columns: { pc: 12, tablet: 12, mobile: 12 },
};

const editorData = {
  id: "test-editor",
  value: "yes",
  name: "test-editor",
  disabled: false,
  required: true,
  pattern: "(test)",
  label: "Test editor",
  tabId: "1",
  columns: { pc: 12, tablet: 12, mobile: 12 },
};

const tableData = {
  title: "Table title",
  minWidth: "sm",
  header: ["Header 1", "Header 2", "Header 3"],
  positions: [4, 4, 4],
  items: [
    [
      {
        type: "Text",
        data: {
          text: "whitelist-download",
        },
      },
      {
        type: "Text",
        data: {
          text: "whitelist-download",
        },
      },
      {
        type: "Text",
        data: {
          text: "whitelist-download",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "whitelist-download",
        },
      },
      {
        type: "Text",
        data: {
          text: "whitelist-download",
        },
      },
      {
        type: "Text",
        data: {
          text: "whitelist-download",
        },
      },
    ],
  ],
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
        <Table v-bind="tableData" />
      </Grid>
    </GridLayout>
  </DashboardLayout>
</template>
