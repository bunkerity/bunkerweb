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
const tableUnbanId = "table-bans-list";
const unbans = new Set([]);

const tableAddbanId = "table-add-bans";
let addCount = 1;

/**
 *  @name updateTableData
 *  @description Update table data with the send one.
 *  @param {Array} data - The data to update.
 *  @returns {Void}
 */
function updateTableData(tableId, data) {
  const tableEl = tableStore.getTableById(tableId);
  tableEl.clearData();
  tableEl.updateOrAddData(data);
}

/**
 *  @name unbanHandler
 *  @description Define all the unban table actions (submit form, unselect, select...)
 *  @returns {Void}
 */
function unbanHandler() {
  window.addEventListener("click", (e) => {
    // select all rows : set all rows checkbox to yes + add ip to unbans
    if (e.target.closest("button[data-select-rows]")) {
      const tableData = JSON.parse(
        JSON.stringify(tableStore.getDefaultTableDataById(tableUnbanId))
      );
      unbans.clear();

      for (let i = 0; i < tableData.length; i++) {
        const item = tableData[i];
        item.check.setting.value = "yes";
        // add ip to unbans
        unbans.add(item.ip.text);
      }
      updateTableData(tableUnbanId, tableData);
      return;
    }

    // unselect all rows : reset to default the table + clear unbans arrau
    if (e.target.closest("button[data-unselect-rows]")) {
      updateTableData(
        tableUnbanId,
        JSON.parse(
          JSON.stringify(tableStore.getDefaultTableDataById(tableUnbanId))
        )
      );
      // clear unbans
      unbans.clear();
      return;
    }

    // listen to checkbox, look to the state and update unbans base on it
    if (
      e.target.closest("input[type=checkbox]") &&
      e.target.closest(`#${tableUnbanId}`)
    ) {
      const checkboxEl = e.target.closest("input[type=checkbox]");
      const isChecked = checkboxEl.checked;
      const checkboxId = +checkboxEl.getAttribute("data-ban-id");
      const tableEl = tableStore.getTableById(tableUnbanId);
      const tableData = tableEl.getData();
      const item = tableData.find((el) => el.id === checkboxId);
      isChecked ? unbans.add(item.ip.text) : unbans.delete(item.ip.text);
      return;
    }

    // send current selected ips
    if (e.target.closest("button[data-unban]")) {
      // transform unbans to array
      const data = { bans: JSON.stringify([...unbans]) };
      useSubmitForm(data, "/unban", "POST");
    }
  });
}

/**
 *  @name updateItemId
 *  @description Replace default item id by new noe
 *  @param {Object} item - item
 *  @param {String|Number} id - new id
 *  @returns {item} - updated item
 */
function updateItemId(item, id) {
  item.id = +id;
  item.ban_end.setting.id = item.ban_end.setting.id.replace("-1", `-${id}`);
  item.ip.setting.id = item.ip.setting.id.replace("-1", `-${id}`);
}

/**
 *  @name addBanHandler
 *  @description Define all the ban table actions (submit form, unselect, select...)
 *  @returns {Void}
 */
function addBanHandler() {
  window.addEventListener("click", (e) => {
    // select all rows : set all rows checkbox to yes + add ip to unbans
    if (e.target.closest("button[data-add-row]")) {
      addCount++;
      const tableData = JSON.parse(
        JSON.stringify(tableStore.getDefaultTableDataById(tableAddbanId))
      );
      const item = JSON.parse(JSON.stringify(tableData[0]));
      updateItemId(item, addCount);
      const tableEl = tableStore.getTableById(tableAddbanId);
      tableEl.addData(item);
      return;
    }

    if (e.target.closest("button[data-delete-all]")) {
      updateTableData(
        tableAddbanId,
        JSON.parse(
          JSON.stringify(tableStore.getDefaultTableDataById(tableAddbanId))
        )
      );
      return;
    }

    // send current selected ips
    if (e.target.closest("button#add-bans-btn")) {
      // transform unbans to array
      const bans = [];
      const tabulatorRows = document
        .querySelector(`#${tableAddbanId}`)
        .querySelectorAll(".tabulator-row");

      console.log();

      for (let i = 0; i < tabulatorRows.length; i++) {
        const row = tabulatorRows[i];
        const ip = row.querySelector("input[name=ip]").value;
        const banEndVal = row
          .querySelector("input[name=ban_end]")
          .getAttribute("data-timestamp");
        const banEnd = !isNaN(banEndVal) ? banEndVal : "";
        bans.push({ ip: ip, ban_end: banEnd, reason: "ui" });
      }
      const data = { bans: JSON.stringify(bans) };
      useSubmitForm(data, "/ban", "POST");
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
  unbanHandler();
  addBanHandler();
});
</script>

<template>
  <DashboardLayout>
    <BuilderBans v-if="bans.builder" :builder="bans.builder" />
  </DashboardLayout>
</template>
