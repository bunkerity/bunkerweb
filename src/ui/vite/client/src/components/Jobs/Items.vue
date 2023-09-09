<script setup>
import ListItem from "@components/List/Item.vue";
import JobsSvgState from "@components/Jobs/Svg/State.vue";
import JobsSvgHistory from "@components/Jobs/Svg/History.vue";
import ButtonBase from "@components/Button/Base.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import { defineProps, defineEmits } from "vue";
import { getJobsCacheNames } from "@utils/jobs";
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
const emits = defineEmits(["cache", "run", "history"]);
</script>

<template>
  <ListItem
    v-for="(item, id) in props.items"
    :class="[id === props.items.length - 1 ? '' : 'border-b']"
  >
    <div class="list-content-item-wrap" v-for="(data, key) in item">
      <span class="pl-4" :class="[props.positions[0]]">{{ key }}</span>
      <span :class="[props.positions[1]]">{{ data["every"] }}</span>
      <div :class="[props.positions[2], 'ml-2']">
        <button @click="$emit('history', { jobName: key })">
          <JobsSvgHistory />
        </button>
      </div>
      <div class="translate-x-3" :class="[props.positions[3]]">
        <JobsSvgState :success="data['reload']" />
      </div>
      <div class="translate-x-4" :class="[props.positions[4]]">
        <JobsSvgState :success="data['history'][0]['success']" />
      </div>
      <div :class="[props.positions[5]]">
        <span>{{ data["history"][0]["end_date"] }}</span>
      </div>
      <div :class="[props.positions[6]]">
        <SettingsSelect
          v-if="data['cache'].length > 0"
          @inp="(v) => $emit('cache', { jobName: key, cacheName: v })"
          :settings="{
            id: 'cache-files',
            value: 'select to download',
            values: getJobsCacheNames(data['cache']),
          }"
        />
      </div>
      <div :class="[props.positions[7], 'flex justify-center']">
        <ButtonBase
          color="valid"
          size="lg"
          @click="$emit('run', { jobName: key })"
        >
          run
        </ButtonBase>
      </div>
    </div>
  </ListItem>
</template>
