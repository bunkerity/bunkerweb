<script setup>
import { reactive, onBeforeMount, triggerRef } from "vue";
import Icons from "@components/Widget/Icons.vue";
import InputList from "@components/Forms/Field/List.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";

const list = {
  id: "test-input",
  value: "yes no maybe",
  name: "test-list",
  label: "Test list",
  inpType: "list",
  onlyDown: true,
  popovers: [
    {
      text: "This is a popover text",
      iconName: "info",
    },
  ],
  columns: { pc: 12, tablet: 12, mobile: 12 },
};
</script>

<template>
  <DashboardLayout>
    <GridLayout :columns="{ pc: 12, tablet: 12, mobile: 12 }">
      <!-- widget grid -->
      <InputList v-bind="list" />
    </GridLayout>
  </DashboardLayout>
</template>
