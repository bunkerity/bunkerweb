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

  function setBannerVisible(bool) {
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

  function setReadOnly(bool) {
    isReadOnly.value = bool;
  }

  return { isReadOnly, setReadOnly };
});

/**
 *  @name useDisplayStore
 *  @description This store is used to share the display state of the components.
 *  This store will handle key-value with the display group name and the current component display name.
 *  This will allow to show or hide components based on the display group name. This is useful with tabs of after a button action to show a specific component.
 *  Because of builder approach, we can't directly update the display state on components (like in buttons) unless in dedicated tabs component.
 *  In case we can't update state on component, we need to declare the store on the page level, and add a script to switch the state by listening to components with classic selectors.
 *  @returns {object} - Object with the display data.
 */
export const useDisplayStore = defineStore("display", () => {
  const display = ref({});

  function setDisplay(groupName, componentName) {
    display.value[groupName] = String(componentName);
  }

  function getDisplayByGroupName(groupName) {
    return display.value[groupName];
  }

  function getDisplays() {
    return display.value;
  }

  function isCurrentDisplay(groupName, componentName) {
    return display.value[groupName] === String(componentName);
  }

  return {
    display,
    setDisplay,
    getDisplayByGroupName,
    getDisplays,
    isCurrentDisplay,
  };
});

/**
 *  @name useTableStore
 *  @description Store instiantiate Tabulator.js table using id prop component.
 *  This is useful to get another component interact with the table and do some actions (delete, update, etc).
 *  @returns {object{boolean, function}} - Object with functions to get one are all tables.
 */
export const useTableStore = defineStore("table", () => {
  const tables = ref({});
  const tablesDefaultData = ref({});

  function setTable(id, tabulatorInstance) {
    tables.value[id] = tabulatorInstance;
  }

  function setDefaultTableData(id, data) {
    tablesDefaultData.value[id] = data;
  }

  function getDefaultTableDataById(id) {
    return tablesDefaultData.value[id];
  }

  function getDefaultTablesData() {
    return tablesDefaultData.value;
  }

  function getTableById(id) {
    return tables.value[id];
  }

  function getTables() {
    return tables.value;
  }

  function removeTable(id) {
    delete tables.value[id];
  }

  function isTable(id) {
    return !!(id in tables.value);
  }

  return {
    setTable,
    getTableById,
    getTables,
    removeTable,
    isTable,
    setDefaultTableData,
    getDefaultTableDataById,
    getDefaultTablesData,
  };
});
