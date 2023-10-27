<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import JobsModalHistory from "@components/Jobs/Modal/History.vue";
import ListBase from "@components/List/Base.vue";
import JobsItems from "@components/Jobs/Items.vue";
import ApiState from "@components/Api/State.vue";

import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { reactive, computed, onMounted } from "vue";
import { getJobsByFilter, getJobsIntervalList } from "@utils/jobs.js";

const feedbackStore = useFeedbackStore();

const positions = [
  "col-span-2",
  "col-span-1",
  "col-span-1",
  "col-span-1",
  "col-span-1",
  "col-span-2",
  "col-span-3",
  "col-span-1",
];

const header = [
  "Name",
  "Every",
  "History",
  "Reload",
  "Success",
  "Last run",
  "Cache",
  "Action",
];

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  name: "",
  reload: "all",
  success: "all",
  every: "all",
});

// Plugins data to render components
const jobs = reactive({
  isPend: false,
  isErr: false,
  // Never modify this unless refetch
  data: [],
  total: computed(() => Object.keys(jobs.data).length),
  reload: computed(() => {
    return Object.values(jobs.data).filter((item) => item["reload"] !== false)
      .length;
  }),
  success: computed(() => {
    return Object.values(jobs.data).filter(
      (item) => item["history"][0]["success"] !== false,
    ).length;
  }),
  setup: computed(() => {
    // Change to array and keep name
    const cloneData = JSON.parse(JSON.stringify(jobs.data));
    const dataArr = [];
    for (const [key, value] of Object.entries(cloneData)) {
      dataArr.push({ [key]: cloneData[key] });
    }

    // Filter data to display
    const filter = getJobsByFilter(dataArr, filters);
    return filter;
  }),
});

async function getJobs() {
  await fetchAPI("/api/jobs", "GET", null, jobs, feedbackStore.addFeedback);
}

const run = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

async function runJob(data) {
  await fetchAPI(
    `/api/jobs/${data.jobName}/run?method=ui`,
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

async function downloadFile(data) {
  await fetchAPI(
    `/api/jobs/${data.jobName}/cache/${data.cacheName}`,
    "GET",
    null,
    download,
    feedbackStore.addFeedback,
  );
}

const history = reactive({
  isOpen: false,
  jobName: "",
  data: [],
});

function showHistory(data) {
  history.jobName = data.jobName;
  history.data = jobs.data[data.jobName]["history"];
  history.isOpen = true;
}

onMounted(() => {
  getJobs();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="jobs.isErr"
      :isPend="jobs.isPend"
      :textState="{
        isPend: 'Try retrieve jobs',
        isErr: 'Error retrieving jobs',
      }"
    />
    <CardBase
      v-if="!jobs.isErr && !jobs.isPend"
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      label="info"
    >
      <CardItemList
        :items="[
          { label: 'jobs total', value: jobs.total },
          { label: 'jobs reload', value: jobs.reload },
          { label: 'jobs success', value: jobs.success },
        ]"
      />
    </CardBase>
    <CardBase
      v-if="!jobs.isErr && !jobs.isPend"
      class="z-10 h-fit col-span-12 md:col-span-8 xl:col-span-8 2xl:col-span-5 3xl:col-span-4"
      label="filter"
    >
      <SettingsLayout class="sm:col-span-6" label="Search" name="keyword">
        <SettingsInput
          @inp="(v) => (filters.name = v)"
          :settings="{
            id: 'keyword',
            type: 'text',
            value: '',
            placeholder: 'keyword',
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="sm:col-span-6"
        label="Success state"
        name="success-state"
      >
        <SettingsSelect
          @inp="
            (v) =>
              (filters.success =
                v === 'all' ? 'all' : v === 'true' ? true : false)
          "
          :settings="{
            id: 'success-state',
            value: 'all',
            values: ['all', 'true', 'false'],
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="sm:col-span-6"
        label="Reload state"
        name="reload-state"
      >
        <SettingsSelect
          @inp="
            (v) =>
              (filters.reload =
                v === 'all' ? 'all' : v === 'true' ? true : false)
          "
          :settings="{
            id: 'reload-state',
            value: 'all',
            values: ['all', 'true', 'false'],
          }"
        />
      </SettingsLayout>
      <SettingsLayout class="sm:col-span-6" label="Interval" name="every">
        <SettingsSelect
          @inp="(v) => (filters.every = v)"
          :settings="{
            id: 'every',
            value: 'all',
            values: getJobsIntervalList(),
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase
      v-if="!jobs.isErr && !jobs.isPend"
      class="col-span-12 overflow-x-auto overflow-y-hidden"
      label="jobs"
    >
      <ListBase
        class="min-w-[1100px] col-span-12"
        :header="header"
        :positions="positions"
      >
        <JobsItems
          @cache="(v) => downloadFile(v)"
          @run="(v) => runJob(v)"
          @history="(v) => showHistory(v)"
          :positions="positions"
          :items="jobs.setup"
        >
        </JobsItems>
      </ListBase>
    </CardBase>
    <JobsModalHistory
      :history="history.data"
      :jobName="history.jobName"
      :isOpen="history.isOpen"
      @close="history.isOpen = false"
    />
  </Dashboard>
</template>
