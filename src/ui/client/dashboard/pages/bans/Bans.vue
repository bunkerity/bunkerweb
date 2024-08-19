<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderBans from "@components/Builder/Bans.vue";
import { useGlobal, useSubmitForm } from "@utils/global.js";
import { useDisplayStore } from "@store/global.js";

/**
 *  @name Page/Bans.vue
 *  @description This component is the bans page.
 */

// Set default store
const displayStore = useDisplayStore();
displayStore.setDisplay("main", 0);

const bans = reactive({
  builder: "",
});

// Bans table actions
import { useTableStore } from "@store/global.js";

const tableStore = useTableStore();
const tableId = "table-bans-list";
const bansToSubmit = new Set([]);

/**
 *  @name updateTableData
 *  @description Update table data with the send one.
 *  @param {Array} data - The data to update.
 *  @returns {Void}
 */
function updateTableData(data) {
  const tableEl = tableStore.getTableById(tableId);
  tableEl.clearData();
  tableEl.updateOrAddData(data);
}

/**
 *  @name banActions
 *  @description Define all the ban table actions (submit form, unselect, select...)
 *  @returns {Void}
 */
function banActions() {
  window.addEventListener("click", (e) => {
    // select all rows : set all rows checkbox to yes + add ip to bansToSubmit
    if (e.target.closest("button[data-select-rows]")) {
      const tableData = JSON.parse(
        JSON.stringify(tableStore.getDefaultTableDataById(tableId))
      );
      bansToSubmit.clear();

      for (let i = 0; i < tableData.length; i++) {
        const item = tableData[i];
        item.check.setting.value = "yes";
        // add ip to bansToSubmit
        bansToSubmit.add(item.ip.text);
      }
      updateTableData(tableData);
      return;
    }

    // unselect all rows : reset to default the table + clear bansToSubmit arrau
    if (e.target.closest("button[data-unselect-rows]")) {
      updateTableData(
        JSON.parse(JSON.stringify(tableStore.getDefaultTableDataById(tableId)))
      );
      // clear bansToSubmit
      bansToSubmit.clear();
      return;
    }

    // listen to checkbox, look to the state and update bansToSubmit base on it
    if (
      e.target.closest("input[type=checkbox]") &&
      e.target.closest("[data-is='table']")
    ) {
      const checkboxEl = e.target.closest("input[type=checkbox]");
      const isChecked = checkboxEl.checked;
      const checkboxId = +checkboxEl.getAttribute("data-ban-id");
      const tableEl = tableStore.getTableById(tableId);
      const tableData = tableEl.getData();
      const item = tableData.find((el) => el.id === checkboxId);
      isChecked
        ? bansToSubmit.add(item.ip.text)
        : bansToSubmit.delete(item.ip.text);
      return;
    }

    // send current selected ips
    if (e.target.closest("button[data-unban]")) {
      // transform bansToSubmit to array
      const data = { bans: JSON.stringify([...bansToSubmit]) };
      useSubmitForm(data, "/unban", "POST");
    }
  });
}

onBeforeMount(() => {
  // Get builder data
  const dataAtt = "data-server-builder";
  const dataEl = document.querySelector(`[${dataAtt}]`);
  const data =
    dataEl && !dataEl.getAttribute(dataAtt).includes(dataAtt)
      ? JSON.parse(atob(dataEl.getAttribute(dataAtt)))
      : {};
  bans.builder = data;
});

onMounted(() => {
  // Set the page title
  useGlobal();
  banActions();
});
</script>

<template>
  <DashboardLayout>
    <BuilderBans v-if="bans.builder" :builder="bans.builder" />
  </DashboardLayout>
</template>
