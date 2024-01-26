<script setup>
import ListItem from "@components/List/Item.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsDatepicker from "@components/Settings/Datepicker.vue";

import { defineProps } from "vue";
const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
  positions: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <ListItem
    v-for="(item, id) in props.items"
    :class="[
      id === props.items.length - 1 ? '' : 'border-b',
      item.isMatchFilter ? '' : 'hidden',
      'py-1 ',
    ]"
  >
    <td class="pl-2" :class="[props.positions[0]]">
      <SettingsLayout
        :showLabel="false"
        :label="$t('reporting_header_date')"
        :name="`reporting-${id}`"
      >
        <SettingsDatepicker
          :settings="{
            id: `reporting-${id}`,
            disabled: true,
          }"
          :defaultDate="Date.parse(item.date)"
        />
      </SettingsLayout>
    </td>
    <td class="ml-2" :class="[props.positions[1]]">{{ item.ip }}</td>
    <td class="ml-2" :class="[props.positions[2]]">
      {{ item.country }}
    </td>
    <td :class="[props.positions[3], 'ml-2']">
      {{ item.method }}
    </td>
    <td class="ml-2" :class="[props.positions[4]]">{{ item.code }}</td>
    <td class="ml-2" :class="[props.positions[5]]">{{ item.user_agent }}</td>
    <td class="ml-2" :class="[props.positions[6]]">{{ item.reason }}</td>
    <td class="ml-2" :class="[props.positions[7]]">{{ item.data }}</td>
  </ListItem>
</template>
