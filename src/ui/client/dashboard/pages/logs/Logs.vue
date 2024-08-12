<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderLogs from "@components/Builder/Logs.vue";
import { useGlobal } from "@utils/global";

/**
*  @name Page/Logs.vue
*  @description This component is the logd page.
  This page allow to choose log files and view the logs.
*/

const logs = reactive({
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
  logs.builder = data;
});

/**
 *  @name getLogContent
 *  @description Redirect to the same page but with log name as query parameter to get the content of the log.
 *  @returns {Void}
 */
function getLogContent() {
  window.addEventListener(
    "click",
    (e) => {
      // Case not wanted element
      if (!e.target.hasAttribute("data-setting-value")) return;
      if (
        !e.target.closest("[data-field-container]").querySelector("[data-log]")
      )
        return;

      const value = e.target.getAttribute("data-setting-value");
      const url = new URL(location.href);
      url.searchParams.set("file", value);
      // go to url
      location.href = url;
    },
    true
  );
}

onMounted(() => {
  // Set the page title
  useGlobal();
  getLogContent();
});
</script>

<template>
  <DashboardLayout>
    <div class="col-span-12 grid grid-cols-12 card">
      <BuilderLogs v-if="logs.builder" :builder="logs.builder" />
    </div>
  </DashboardLayout>
</template>
