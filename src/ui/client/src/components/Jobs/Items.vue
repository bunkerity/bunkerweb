<script setup>
import ListItem from "@components/List/Item.vue";
import JobsSvgState from "@components/Jobs/Svg/State.vue";
import JobsSvgHistory from "@components/Jobs/Svg/History.vue";
import ButtonBase from "@components/Button/Base.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import { defineProps, reactive } from "vue";
import { fetchAPI } from "@utils/api.js";
import { getJobsCacheNames, getServId } from "@utils/jobs.js";
import { useFeedbackStore, useRefreshStore } from "@store/global.js";
import { useModalStore } from "@store/jobs.js";

const modalStore = useModalStore();
const feedbackStore = useFeedbackStore();
const refreshStore = useRefreshStore();

const props = defineProps({
  items: {
    type: Array,
    required: true,
    default: [],
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
    feedbackStore.addFeedback,
  )
    .then((res) => {
      return res.json();
    })
    .then((data) => {
      if (data.type === "success") {
        return refreshStore.refresh();
      }
    });
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

function showHistory(name, history) {
  modalStore.data = { name: name, history: history };
  modalStore.isOpen = true;
}
</script>

<template>
  <ListItem
    v-for="(item, id) in props.items"
    :class="[id === props.items.length - 1 ? '' : 'border-b', 'py-2']"
  >
    <td class="ml-2" :class="[props.positions[0]]">
      {{ Object.keys(item)[0] }}
    </td>
    <td class="ml-2" :class="[props.positions[1]]">
      {{ item[Object.keys(item)[0]]["every"] }}
    </td>
    <td class="ml-4" :class="[props.positions[2]]">
      <button
        :aria-describedby="`${Object.keys(item)[0]}-history-text-${id}`"
        :aria-controls="`history-modal`"
        :aria-expanded="modalStore.isOpen ? 'true' : 'false'"
        @click="
          showHistory(
            Object.keys(item)[0],
            item[Object.keys(item)[0]]['history'],
          )
        "
      >
        <span
          :id="`${Object.keys(item)[0]}-history-text-${id}`"
          class="sr-only"
        >
          {{ $t("jobs_actions_show_history") }}
        </span>
        <JobsSvgHistory />
      </button>
    </td>
    <td class="translate-x-3 ml-2.5" :class="[props.positions[3]]">
      <JobsSvgState :success="item[Object.keys(item)[0]]['reload']" />
    </td>
    <td class="translate-x-4 ml-2.5" :class="[props.positions[4]]">
      <JobsSvgState
        :success="item[Object.keys(item)[0]]['history'][0]['success']"
      />
    </td>
    <td class="ml-3" :class="[props.positions[5]]">
      <span>{{ item[Object.keys(item)[0]]["history"][0]["end_date"] }}</span>
    </td>
    <td class="mx-4" :class="[props.positions[6]]">
      <SettingsSelect
        v-if="item[Object.keys(item)[0]]['cache'].length > 0"
        :settings="{
          id: `cache-${Object.keys(item)[0]}-${id}`,
          value: $t('jobs_actions_cache_download'),
          values: getJobsCacheNames(item[Object.keys(item)[0]]['cache']),
        }"
        @inp="(v) => downloadFile(Object.keys(item)[0], v)"
      >
      </SettingsSelect>
    </td>
    <td :class="[props.positions[7], 'flex justify-center']">
      <ButtonBase
        type="submit"
        class="py-1.5"
        color="valid"
        size="lg"
        @click.prevent="runJob(Object.keys(item)[0])"
      >
        {{ $t("jobs_actions_run") }}
      </ButtonBase>
    </td>
  </ListItem>
</template>
