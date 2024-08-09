<script setup>
import { defineProps, onUpdated, reactive, watch } from "vue";
import Container from "@components/Widget/Container.vue";

import Input from "@components/Forms/Field/Input.vue";
import Select from "@components/Forms/Field/Select.vue";

import { useFilter } from "@utils/filter.js";
/**
 *  @name Widget/Filter.vue
 *  @description This component allow to filter any data object or array with a list of filters.
 *  For the moment, we have 2 types of filters: select and keyword.
 *  We have default values that avoid filter ("all" for select and "" for keyword).
 *  Filters are fields so we need to provide a "field" key with same structure as a Field.
 *  We have to define "keys" that will be the keys the filter value will check.
 *  We can set filter "default" in order to filter the base keys of an object.
 *  We can set filter "settings" in order to filter settings, data must be an advanced template.
 *  We can set filter "table" in order to filter table items.
 *  Check example for more details.
 *  @example
 *    [
 *      {
 *        filter: "default", // or "settings"  or "table"
 *        type: "select",
 *        value: "all",
 *        keys: ["type"],
 *        field: {
 *          inpType: "select",
 *          id: uuidv4(),
 *          value: "all",
 *          // add 'all' as first value
 *          values: ["all"].concat(plugin_types),
 *          name: uuidv4(),
 *          onlyDown: true,
 *          label: "inp_select_plugin_type",
 *          popovers: [
 *            {
 *              text: "inp_select_plugin_type_desc",
 *              iconName: "info",
 *            },
 *          ],
 *          columns: { pc: 3, tablet: 4, mobile: 12 },
 *        },
 *      },
 *    ]
 *  @param {array} [filters=[]] - Fields with additional data to be used as filters.
 *  @param {object|array} [data={}] - Data object or array to filter. Emit a filter event with the filtered data.
 *  @param {string} [containerClass=""] - Additional class for the container.
 */

const props = defineProps({
  filters: {
    type: Array,
    required: false,
    default: [],
  },
  data: {
    type: Object,
    required: false,
    default: {},
  },
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
});

const emits = defineEmits(["filter"]);

const filters = reactive({
  base: JSON.parse(JSON.stringify(props.filters)),
  bufferCount: 0,
  isFiltering: false,
});

watch(
  () => props.data,
  () => {
    filterData();
  },
  { deep: true },
);

/**
 *  @name startFilter
 *  @description  Filter the given data using the available filters from a filter object.
 *  @param {object} filter - Filter object to apply.
 *  @param {string} value - Value to filter.
 *  @returns {emits} - Emit a filter event with the filtered data.
 */
function startFilter(filter = {}, value) {
  // Case we have new filter value, update it
  // Loop on filter.base and update the "value" key when matching filterName
  if (filter?.filterName && value !== null) {
    filters.base.forEach((f) => {
      if (f.filterName === filter.filterName) {
        f.value = value;
      }
    });
  }

  // Start filtering
  let template = JSON.parse(JSON.stringify(props.data));
  const getFilters = JSON.parse(JSON.stringify(filters.base));

  // Base keys filtering (like plugin)
  const defaultFilters = getFilters.filter((f) => f.filter === "default");
  if (defaultFilters.length) template = useFilter(template, defaultFilters);

  // Specific settings filtering from advanced template
  const filterSettings = getFilters.filter((f) => f.filter === "settings");
  if (filterSettings.length) {
    filterRegularSettings(filterSettings, template);
    filterMultiplesSettings(filterSettings, template);
    // Case no settings or multiple found, remove plugin
    template = template.filter((plugin) => {
      return (
        Object.keys(plugin?.settings || {}).length > 0 ||
        Object.keys(plugin?.multiples || {}).length > 0
      );
    });
  }

  // Base keys filtering (like plugin)
  const tableFilters = getFilters.filter((f) => f.filter === "table");
  if (tableFilters.length) {
    // Loop on each array of array
    for (let i = 0; i < template.length; i++) {
      const row = template[i];
      // We need to check one complete row on filter
      // So we need to merge all keys of each column
      const mergeRow = {};
      row.forEach((item) => {
        Object.keys(item).forEach((key) => {
          mergeRow[key] = item[key];
        });
      });
      const newRow = useFilter([mergeRow], tableFilters);
      // Case newRow is empty array, didn't pass filter
      if (Array.isArray(newRow) && newRow.length <= 0) template[i] = [];
    }
    // Remove empty row
    template = template.filter((row) => row.length > 0);
  }
  emits("filter", template);
}

/**
 *  @name filterData
 *  @description Add a buffer to wait for multiple inputs before filtering the data.
 *  Then filter data with the given filter and value.
 *  @param {object} filter - Filter object to apply.
 *  @param {string} value - Value to filter.
 *  @returns {void}
 */
function filterData(filter = {}, value = null) {
  // Wait for buffer input
  filters.bufferCount++;
  const currBufferCount = filters.bufferCount;
  // Wait time to check if not another input (count) to filter
  setTimeout(() => {
    // Case another input, don't filter and wait again
    if (currBufferCount < filters.bufferCount) return;
    startFilter(filter, value);
  }, 50);
}

/**
 *  @name filterRegularSettings
 *  @description Allow to filter plugin settings from a regular template.
 *  @param {object} filterSettings - Filters to apply
 *  @param {object} template - Template to filter
 *  @returns {void}
 */
function filterRegularSettings(filterSettings, template) {
  template.forEach((plugin, id) => {
    // loop on plugin settings dict
    const settings = [];
    for (const [key, value] of Object.entries(plugin.settings)) {
      // add to value the key as setting_name
      settings.push({ ...value, setting_name: key });
    }
    const filterSettingsData = useFilter(settings, filterSettings);
    // Transform list of dict by a dict of dict with setting_name as key and add update plugin settings
    const settingsData = {};
    filterSettingsData.forEach((setting) => {
      settingsData[setting.setting_name] = setting;
    });
    template[id].settings = settingsData;
  });
}

/**
 *  @name filterMultiplesSettings
 *  @description Allow to filter plugin multiples settings from a regular template.
 *  @param {object} filterSettings - Filters to apply
 *  @param {object} template - Template to filter
 *  @returns {void}
 */
function filterMultiplesSettings(filterSettings, template) {
  const multiples = [];
  // Format to filter
  for (let i = 0; i < template.length; i++) {
    const plugin = template[i];
    if (!plugin?.multiples || Object.keys(plugin?.multiples || {}).length <= 0)
      continue;
    for (const [multName, multGroups] of Object.entries(plugin.multiples)) {
      for (const [groupName, groupSettings] of Object.entries(multGroups)) {
        // Check if inpid is matching a groupSettings key
        for (const [key, value] of Object.entries(groupSettings)) {
          multiples.push({
            ...value,
            setting_name: key,
            plugin_id: plugin.id,
            group_name: groupName,
            mult_name: multName,
          });
        }
      }
    }
  }

  // Remove multiples from template
  template.forEach((plugin) => {
    delete plugin.multiples;
  });
  // Add filtered multiples
  const filterSettingsData = useFilter(multiples, filterSettings);

  for (let i = 0; i < filterSettingsData.length; i++) {
    const setting = filterSettingsData[i];
    const pluginId = setting?.plugin_id;
    const groupName = setting?.group_name;
    const multName = setting?.mult_name;
    const settingName = setting?.setting_name;
    delete setting.plugin_id;
    delete setting.group_name;
    delete setting.setting_name;
    // Find the plugin in template
    const pluginIndex = template.findIndex((plugin) => plugin.id === pluginId);
    if (pluginIndex < 0) continue;
    if (!("multiples" in template[pluginIndex]))
      template[pluginIndex]["multiples"] = {};

    if (!(multName in template[pluginIndex]["multiples"]))
      template[pluginIndex]["multiples"][multName] = {};
    if (!(groupName in template[pluginIndex]["multiples"][multName]))
      template[pluginIndex]["multiples"][multName][groupName] = {};

    template[pluginIndex]["multiples"][multName][groupName][settingName] =
      setting;
  }
}
</script>

<template>
  <Container v-if="filters.base" :containerClass="'layout-settings'">
    <slot></slot>
    <template v-for="filter in filters.base">
      <Input
        v-if="filter.type === 'keyword'"
        @inp="(v) => filterData(filter, v)"
        v-bind="filter.field"
      />
      <Select
        v-if="filter.type === 'select'"
        @inp="(v) => filterData(filter, v)"
        v-bind="filter.field"
      />
    </template>
  </Container>
</template>
