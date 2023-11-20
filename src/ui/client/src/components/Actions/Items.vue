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
      'py-1',
    ]"
  >
    <div class="list-content-item-wrap">
      <span class="pl-2" :class="[props.positions[0]]">{{
        item["method"].toUpperCase()
      }}</span>
      <span class="ml-2" :class="[props.positions[1]]">{{
        item["title"]
      }}</span>
      <span class="ml-3" :class="[props.positions[2]]">{{
        item["description"]
      }}</span>
      <div :class="[props.positions[3], 'ml-2']">
        <SettingsLayout label="" :name="`action-${id}`">
          <SettingsDatepicker
            :settings="{
              id: `action-${id}`,
              disabled: true,
            }"
            :defaultDate="Date.parse(item.date)"
          />
        </SettingsLayout>
      </div>
      <span class="ml-9" :class="[props.positions[4]]"
        >{{ item["api_method"] }}
      </span>
    </div>
  </ListItem>
</template>
