<script setup>
import { defineProps, reactive } from "vue";
import Container from "@components/Widget/Container.vue";

import Input from "@components/Forms/Field/Input.vue";
import Select from "@components/Forms/Field/Select.vue";

import { useFilter } from "@utils/form.js";
/**
  @name Widget/Filter.vue
  @description This component allow to filter any data object or array with a list of filters.
  For the moment, we have 2 types of filters: select and keyword.
  We have default values that avoid filter ("all" for select and "" for keyword).
  Filters are fields so we need to provide a "field" key with same structure as a Field.
  We have to define "keys" that will be the keys the filter value will check.
  We can set filter "default" in order to filter the base keys of an object.
  We can set filter "settings" in order to filter settings, data must be an advanced template.
  We can set filter "table" in order to filter table items.
  Check example for more details.
  @example
    [
      {
        filter: "default", // or "settings"  or "table"
        type: "select",
        value: "all",
        keys: ["type"],
        field: {
          inpType: "select",
          id: uuidv4(),
          value: "all",
          // add 'all' as first value
          values: ["all"].concat(plugin_types),
          name: uuidv4(),
          onlyDown: true,
          label: "inp_select_plugin_type",
          popovers: [
            {
              text: "inp_select_plugin_type_desc",
              iconName: "info",
            },
          ],
          columns: { pc: 3, tablet: 4, mobile: 12 },
        },
      },
      ...
    ]
  @param {array} [filters=[]] - Fields with additional data to be used as filters.
  @param {object|array} [data={}] - Data object or array to filter. Emit a filter event with the filtered data.
  @param {string} [containerClass=""] - Additional class for the container.
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
});

function filterData(filter, value) {
  // Loop on filter.base and update the "value" key when matching filterName
  filters.base.forEach((f) => {
    if (f.filterName === filter.filterName) {
      f.value = value;
    }
  });

  // Start filtering
  let template = JSON.parse(JSON.stringify(props.data));
  const getFilters = JSON.parse(JSON.stringify(filters.base));

  // Base keys filtering (like plugin)
  const defaultFilters = getFilters.filter((f) => f.filter === "default");
  if (defaultFilters.length) template = useFilter(template, defaultFilters);

  // Specific settings filtering from advanced template
  const filterSettings = getFilters.filter((f) => f.filter === "settings");
  if (filterSettings.length) {
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

    // Case no settings found, remove plugin
    template = template.filter((plugin) => {
      return Object.keys(plugin.settings).length > 0;
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
