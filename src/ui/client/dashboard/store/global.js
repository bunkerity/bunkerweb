import { defineStore } from "pinia";
import { ref } from "vue";

/**
 *  @name useBannerStore
 *  @description Store to share the current banner state (visible or not).
 *  This is useful to update components, specially fixed ones, related to the banner visibility.
 *  @returns {object} - Object with the banner state, banner class and function to set the banner visibility.
 */
export const useBannerStore = defineStore("banner", () => {
  const isBanner = ref(true);
  const bannerClass = ref("banner");

  async function setBannerVisible(bool) {
    isBanner.value = bool;
    bannerClass.value = bool ? "banner" : "no-banner";
  }

  return { isBanner, bannerClass, setBannerVisible };
});

/**
 *  @name useReadonlyStore
 *  @description Store to share the current readonly state (true or false).
 *  This is useful to unable or enable some inputs or actions related to the readonly state.
 *  @returns {object} - Object with the readonly state and function to set the readonly state.
 */
export const useReadonlyStore = defineStore("readonly", () => {
  const isReadOnly = ref(true);

  async function setReadOnly(bool) {
    isReadOnly.value = bool;
  }

  return { isReadOnly, setReadOnly };
});

/**
 *  @name useTableStore
 *  @description Store instiantiate Tabulator.js table using id prop component.
 *  This is useful to get another component interact with the table and do some actions (delete, update, etc).
 *  @returns {object{boolean, function}} - Object with functions to get one are all tables.
 */
export const useTableStore = defineStore("table", () => {
  const tables = ref({});

  async function setTable(id, tabulatorInstance) {
    tables.value[id] = tabulatorInstance;
  }

  function getTableById(id) {
    return tables.value[id];
  }

  function getTables() {
    return tables.value;
  }

  return { setTable, getTableById, getTables };
});
