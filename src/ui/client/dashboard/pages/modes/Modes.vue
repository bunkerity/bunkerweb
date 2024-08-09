<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderModes from "@components/Builder/Modes.vue";
import { useGlobal } from "@utils/global";

/**
 *  @name Page/Modes.vue
 *  @description This component is the modes page.
 *  This page displays the raw form and additional actions to manage or create a service.
 */

const modes = reactive({
  builder: "",
});

onBeforeMount(() => {
  // Get builder data
  const dataAtt = "data-server-builder";
  const dataEl = document.querySelector(`[${dataAtt}]`);
  const data =
    dataEl && !dataEl.getAttribute(dataAtt).includes(dataAtt)
      ? JSON.parse(atob(dataEl.getAttribute(dataAtt)))
      : {};
  modes.builder = data;
});

onMounted(() => {
  // Set the page title
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <div class="col-span-12 grid grid-cols-12 card">
      <BuilderModes v-if="modes.builder" :builder="modes.builder" />
    </div>
  </DashboardLayout>
</template>
