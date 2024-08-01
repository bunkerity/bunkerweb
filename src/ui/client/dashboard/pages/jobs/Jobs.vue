<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderJobs from "@components/Builder/Jobs.vue";
import { useGlobal } from "@utils/global";

/**
*  @name Page/Jobs.vue
*  @description This component is the jobs page.
  This page displays some useful information about the jobs.
*/

const jobs = reactive({
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
  jobs.builder = data;
});

/**
 *  @name getLastArrItem
 *  @description Get the last item if the first and last characters are matching params.
 *  @param {string} startStr - The start string to check.
 *  @param {string} endStr - The end string to check.
 *  @returns {null|string} - The last item or null.
 */
function getLastArrItem(startStr, endStr, array) {
  return array[array.length - 1].startsWith(startStr) &&
    array[array.length - 1].endsWith(endStr)
    ? array.pop().replace(startStr, "").replace(endStr, "").trim()
    : null;
}

/**
 *  @name downloadCacheEvent
 *  @description Get the needed cache file information from a job and create a download link to download the file.
 *  @returns {void}
 */
function downloadCacheEvent() {
  window.addEventListener(
    "click",
    (e) => {
      // Case not wanted element
      if (!e.target.hasAttribute("data-select-item")) return;
      if (!e.target.closest("[data-table-body]")) return;

      const value = e.target.getAttribute("data-setting-value");
      // Get needed values to download the cache file
      const values = value.split(" ");
      // In case the last element start with "[" and end with "]", this is the serviceId
      const serviceId = getLastArrItem("[", "]", values);
      // Merge the rest of the values and trim, this is the file name
      const fileName = values.join(" ").trim();
      // Others values are on the toggle dropdown btn attributes
      const pluginId = e.target
        .closest("[data-field-container]")
        .querySelector("[data-select-dropdown]")
        .getAttribute("data-plugin-id");
      const jobName = e.target
        .closest("[data-field-container]")
        .querySelector("[data-select-dropdown]")
        .getAttribute("data-job-name");

      if (!pluginId && !fileName && !jobName) return;

      const fileArg = fileName ? `file_name=${fileName}` : "";
      const jobNameArg = jobName ? `&job_name=${jobName}` : "";
      const pluginArg = pluginId ? `&plugin_id=${pluginId}` : "";
      const serviceArg = serviceId ? `&service_id=${serviceId}` : "";
      const url = `${location.href}/download?${fileArg}${jobNameArg}${pluginArg}${serviceArg}`;

      const a = document.createElement("a");
      a.href = url;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    },
    true
  );
}

onMounted(() => {
  downloadCacheEvent();
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <BuilderJobs v-if="jobs.builder" :builder="jobs.builder" />
  </DashboardLayout>
</template>
