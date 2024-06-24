<script setup>
import { reactive, onBeforeMount, triggerRef } from "vue";
import Icons from "@components/Widget/Icons.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";

const icon = {
  iconName: "wire",
};
</script>

<template>
  <DashboardLayout>
    <GridLayout :columns="{ pc: 12, tablet: 12, mobile: 12 }">
      <!-- widget grid -->
      <div data-is="menu">
        <Icons v-bind="icon" />
      </div>
    </GridLayout>
  </DashboardLayout>
</template>
