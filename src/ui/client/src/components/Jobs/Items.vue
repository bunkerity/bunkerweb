<script setup>
import ListItem from "@components/List/Item.vue";
import JobsSvgState from "@components/Jobs/Svg/State.vue";
import JobsSvgHistory from "@components/Jobs/Svg/History.vue";
import ButtonBase from "@components/Button/Base.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import { defineProps, defineEmits, reactive, onMounted } from "vue";
import { useFeedbackStore } from "@store/global.js";
import { fetchAPI } from "@utils/api.js";
import { getJobsCacheNames, getServId } from "@utils/jobs.js";

const feedbackStore = useFeedbackStore();

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

onMounted(() => {
  console.log(props.items);
});

const run = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

async function runJob(jobName) {
  await fetchAPI(
    `/api/jobs/run?method=ui&job_name=${jobName}`,
    "POST",
    null,
    run,
    feedbackStore.addFeedback,
  );
}

const download = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

// TODO : GET SERVICE ID for current job name

function dl(content, filename, contentType) {
  if (!contentType) contentType = "application/octet-stream";
  var a = document.createElement("a");
  var blob = new Blob([content], { type: contentType });
  a.href = window.URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  a.remove();
}

async function downloadFile(jobName, cacheName) {
  const servID = getServId(props.items, jobName, cacheName);

  await fetchAPI(
    `/api/jobs/${jobName}/cache/${cacheName}?service_id=${
      servID ? servID : ""
    }`,
    "GET",
    null,
    download,
    feedbackStore.addFeedback,
  )
    .then((res) => {
      return res.json();
    })
    .then((data) => {
      if (data.type === "success") {
        return dl(data.data, `${cacheName}.json`, "text/json");
      }
    });
}

// cache => return cache file name to download
// run => return the job name that need to be run/rerun
const emits = defineEmits(["history"]);
</script>

<template>
  <ListItem
    v-for="(item, id) in props.items"
    :class="[id === props.items.length - 1 ? '' : 'border-b', 'py-2']"
  >
    <td class="pl-4" :class="[props.positions[0]]">{{ item }}</td>
    <td :class="[props.positions[1]]">{{ item["every"] }}</td>
    <td :class="[props.positions[2], 'ml-2']">
      <button @click="$emit('history', { jobName: item })">
        <span class="sr-only">
          {{ $t("jobs_actions_show_history") }}
        </span>
        <JobsSvgHistory />
      </button>
    </td>
    <td class="translate-x-3" :class="[props.positions[3]]">
      <span class="sr-only"
        >{{
          item["reload"]
            ? $t("jobs_state_reload_succeed")
            : $t("jobs_state_reload_failed")
        }}
      </span>
      <JobsSvgState :success="item['reload']" />
    </td>
    <td class="translate-x-4" :class="[props.positions[4]]">
      <span class="sr-only">
        {{
          item["history"][0]["success"]
            ? $t("jobs_state_success_succeed")
            : $t("jobs_state_success_failed")
        }}
      </span>
      <JobsSvgState :success="item['history'][0]['success']" />
    </td>
    <td :class="[props.positions[5]]">
      <span>{{ item["history"][0]["end_date"] }}</span>
    </td>
    <td class="mr-2" :class="[props.positions[6]]">
      <SettingsSelect
        v-if="item['cache'].length > 0"
        :settings="{
          id: `cache-${item}-${id}`,
          value: $t('jobs_actions_cache_download'),
          values: getJobsCacheNames(item['cache']),
        }"
        @inp="(v) => downloadFile(item, v)"
      >
      </SettingsSelect>
    </td>
    <td :class="[props.positions[7], 'flex justify-center']">
      <ButtonBase class="py-1.5" color="valid" size="lg" @click="runJob(item)">
        {{ $t("jobs_actions_run") }}
      </ButtonBase>
    </td>
  </ListItem>
</template>
