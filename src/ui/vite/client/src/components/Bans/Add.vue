<script setup>
import ListBase from "@components/List/Base.vue";
import ListItem from "@components/List/Item.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsDatepicker from "@components/Settings/Datepicker.vue";
import ButtonBase from "@components/Button/Base.vue";

import {reactive} from "vue";

const bans = reactive({
    add : 0,
})

const addPositions = [
  "col-span-3",
  "col-span-3",
  "col-span-3",
  "col-span-3",
];

const addHeader = [
  "IP number",
  "Reason",
  "Ban start",
  "Ban end",
];

function addPrefZero(dateStr) {
  return dateStr.length === 2 ? dateStr : `0${dateStr}`;
}
</script>

<template>
    <div class="col-span-12 grid grid-cols-12">
        <div class="col-span-12 flex justify-center items-center mt-2 mb-6">
            <ButtonBase
                @click="bans.add++"
                color="valid"
                size="normal"
                class="text-sm">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="ml-1 -translate-y-1">
                    Add field
                </span>
             </ButtonBase>
        </div>

          <ListBase v-if="bans.add > 0" 
                class="min-w-[1100px] h-full col-span-12"
                :header="addHeader"
                :positions="addPositions"
              >
              <ListItem
                v-for="index, id in bans.add"
                :class="[id === index - 1 ? '' : 'border-b']"
              >
                <div class="list-content-item-wrap" >
                  <SettingsLayout :class="[addPositions[0], 'mx-2']" label="" :name="`add-ip-${id}`">
                    <SettingsInput
                      @inp="(v) => (filters.name = v)"
                      :settings="{
                        id: `add-ip-${id}`,
                        type: 'text',
                        value: '',
                        placeholder: '127.0.0.1',
                      }"
                    />
                  </SettingsLayout>
                  <SettingsLayout :class="[addPositions[1], 'mx-2']" label="" :name="`add-reason-${id}`">
                    <SettingsInput
                      @inp="(v) => (filters.name = v)"
                      :settings="{
                        id: `add-reason-${id}`,
                        type: 'text',
                        value: '',
                        placeholder: 'Manual',
                      }"
                    />
                  </SettingsLayout>
                  <span :class="[addPositions[2], 'font-sm']">{{ `${addPrefZero(new Date().getMonth().toString())}/${addPrefZero(new Date().getDay().toString())}/${new Date().getFullYear().toString()}` }}</span>
                  <SettingsLayout :class="[addPositions[3], 'mx-2']" label="" :name="`add-ban-date-${id}`">
                    <SettingsDatepicker
                      :settings="{
                        id: `add-ban-date-${id}`,
                      }"
                      :noPickBeforeStamp="Date.parse(new Date())"
                    />
                  </SettingsLayout>
                </div>
              </ListItem>
            </ListBase>
    </div>
  </template>