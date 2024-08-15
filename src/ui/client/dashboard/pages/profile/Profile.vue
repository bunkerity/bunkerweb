<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderProfile from "@components/Builder/Profile.vue";
import { useGlobal } from "@utils/global.js";
import { useDisplayStore } from "@store/global.js";

/**
*  @name Page/Profile.vue
*  @description This component is the profile page.
  This page displays current profile and allows to manage them.
  We are using displayStore and setting ["main", 1] to display the profile list first.
*/

// Set default store
const displayStore = useDisplayStore();
displayStore.setDisplay("main", 0);
displayStore.setDisplay("account", 0);

const profile = reactive({
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
  profile.builder = data;
});

onMounted(() => {
  // Set the page title
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <BuilderProfile v-if="profile.builder" :builder="profile.builder" />
  </DashboardLayout>
</template>
