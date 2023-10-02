<script setup>
import ListItem from "@components/List/Item.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsCheckbox from "@components/Settings/Checkbox.vue";
import { defineProps, defineEmits } from "vue";
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

// cache => return cache file name to download
// run => return the job name that need to be run/rerun
const emits = defineEmits(["check"]);
</script>

<template>
  <ListItem
    v-for="(item, id) in props.items"
    :class="[id === props.items.length - 1 ? '' : 'border-b']"
  >
    <div class="list-content-item-wrap" v-for="(data, key) in item">
      <div :class="[props.positions[0], 'ml-2']">
        <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6"
        label=""
        name="check"
      >
        <SettingsCheckbox
          @inp="(v) => ($emit('check', {state : v, ip : data['ip']}))"
          :settings="{
            id: 'check',
            value: 'no',
          }"
        />
      </SettingsLayout>
      </div>
      <span class="pl-4" :class="[props.positions[1]]">{{ data['ip'] }}</span>
      <span :class="[props.positions[2], 'ml-2']">{{ data["reason"] }}</span>
      <span :class="[props.positions[3], 'ml-2']">{{ data["ban_deb"] }}</span>
      <span :class="[props.positions[4], 'ml-2']">{{ data["ban_end"] }}</span>
    </div>
  </ListItem>
</template>
