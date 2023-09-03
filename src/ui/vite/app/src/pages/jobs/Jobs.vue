<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import JobsStructure from "@components/Jobs/Structure.vue";
import JobsHeader from "@components/Jobs/Header.vue";
import JobsContent from "@components/Jobs/Content.vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { reactive, computed, onMounted } from "vue";
import {
  getJobsReloadNum,
  getJobsSuccessNum,
  getJobsByFilter,
  getJobsIntervalList,
} from "@utils/jobs.js";

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
  "Run",
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
  base: [],
  total: computed(() => jobs.base.length),
  reload: computed(() => getJobsReloadNum(jobs.base)),
  success: computed(() => getJobsSuccessNum(jobs.base)),
  // This run every time reactive data changed (plugin.base or filters)
  setup: computed(() => {
    // Filter data to display
    const cloneBase = JSON.parse(JSON.stringify(jobs.base));
    const filter = getJobsByFilter(cloneBase, filters);
    return filter;
  }),
});

async function getJobs() {
  await fetchAPI("api/jobs", "GET", null, jobs.isPend, jobs.isErr);
}

const run = reactive({
  isPend: false,
  isErr: false,
});

async function runJob(data) {
  await fetchAPI(
    "/api/jobs-run",
    "GET",
    JSON.stringify(data),
    run.isPend,
    run.isErr
  );
}

const download = reactive({
  isPend: false,
  isErr: false,
});

async function downloadFile(data) {
  await fetchAPI(
    `/api/cache?job-name=${data["job-name"]}&file-name=${data["file-name"]}`,
    "GET",
    download.isPend,
    download.isErr
  );
}

onMounted(async () => {
  await getJobs();
});
</script>

<template>
  <Dashboard>
    <CardBase
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
      class="col-span-12 max-w-[1200px] max-h-[55vh] overflow-x-auto overflow-y-visible"
      label="jobs"
    >
      <JobsStructure>
        <JobsHeader :header="header" :positions="positions" />
        <JobsContent
          @cache="(v) => downloadFile(v)"
          @run="(v) => runJob(v)"
          :items="jobs.setup"
          :positions="positions"
        />
      </JobsStructure>
    </CardBase>
  </Dashboard>
</template>
