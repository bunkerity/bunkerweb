<script setup>
import ListItem from "@components/List/Item.vue";
import JobsSvgState from "@components/Jobs/Svg/State.vue";
import JobsSvgHistory from "@components/Jobs/Svg/History.vue";
import ButtonBase from "@components/Button/Base.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import { defineProps, defineEmits, reactive } from "vue";
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
    feedbackStore.addFeedback
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
    feedbackStore.addFeedback
  )
    .then((res) => {
      return res.json();
    })
    .then((data) => {
      if (data.type === "error") return;
      dl(data.data, `${cacheName}.json`, "text/json");
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
    <div class="list-content-item-wrap" v-for="(data, key) in item">
      <span class="pl-4" :class="[props.positions[0]]">{{ key }}</span>
      <span :class="[props.positions[1]]">{{ data["every"] }}</span>
      <div :class="[props.positions[2], 'ml-2']">
        <button @click="$emit('history', { jobName: key })">
          <span class="sr-only">
            {{ $t("jobs.card.jobs.actions.show_history") }}
          </span>
          <JobsSvgHistory />
        </button>
      </div>
      <div class="translate-x-3" :class="[props.positions[3]]">
        <span class="sr-only"
          >{{
            data["reload"]
              ? $t("jobs.card.jobs.state.reload.succeed")
              : $t("jobs.card.jobs.state.reload.failed")
          }}
        </span>
        <JobsSvgState :success="data['reload']" />
      </div>
      <div class="translate-x-4" :class="[props.positions[4]]">
        <span class="sr-only">
          {{
            data["history"][0]["success"]
              ? $t("jobs.card.jobs.state.success.succeed")
              : $t("jobs.card.jobs.state.success.failed")
          }}
        </span>
        <JobsSvgState :success="data['history'][0]['success']" />
      </div>
      <div :class="[props.positions[5]]">
        <span>{{ data["history"][0]["end_date"] }}</span>
      </div>
      <div class="mr-2" :class="[props.positions[6]]">
        <SettingsSelect
          v-if="data['cache'].length > 0"
          :settings="{
            value: $t('jobs.card.jobs.actions.cache_download'),
            values: getJobsCacheNames(data['cache']),
          }"
          @inp="(v) => downloadFile(key, v)"
        >
        </SettingsSelect>
      </div>
      <div :class="[props.positions[7], 'flex justify-center']">
        <ButtonBase class="py-1.5" color="valid" size="lg" @click="runJob(key)">
          {{ $t("jobs.card.jobs.actions.run") }}
        </ButtonBase>
      </div>
    </div>
  </ListItem>
</template>
