<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderBans from "@components/Builder/Bans.vue";
import { useGlobal } from "@utils/global.js";
import { useForm } from "@utils/form.js";

/**
  @name Page/Bans.vue
  @description This component is the ban page.
  This page displays global information about bans, and allow to delete or upload some bans.
*/

const bans = reactive({
  builder: "",
});

onBeforeMount(() => {
  // Get builder data
  const dataAtt = "data-server-builder";
  const dataEl = document.querySelector(`[${dataAtt}]`);
  const data =
    dataEl && !dataEl.getAttribute(dataAtt).includes(dataAtt)
      ? JSON.parse(dataEl.getAttribute(dataAtt))
      : {};
  bans.builder = data;
});

onMounted(() => {
  useGlobal();
  useForm();
});

const builder = [];
</script>

<template>
  <DashboardLayout>
    <BuilderBans v-if="builder" :builder="builder" />
  </DashboardLayout>
</template>
