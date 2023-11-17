<script setup>
import FeedbackAlert from "@components/Feedback/Alert.vue";
import FeedbackLogs from "@components/Feedback/Logs.vue";
import { useFeedbackStore } from "@store/global.js";
import { reactive, watch, onMounted, computed } from "vue";
import TablistBase from "@components/Tablist/Base.vue";
import { getLogsByFilter } from "@utils/logs.js";
import { fetchAPI } from "@utils/api.js";
import { useLogsStore } from "@store/logs.js";

// Handle feedback history panel
const dropdown = reactive({
  isOpen: false,
});

// Share feedback store
// Get changes from another component and display alert
const feedback = useFeedbackStore();

// Delay new last alert should be display
const showDelay = 4000;
const alert = reactive({
  show: true, // Show by default
  showNum: 0, // Track alert num with timeout
  prevNum: 0, // Number of alerts before watcher
});

onMounted(() => {
  // First alert should be hidden after amount of time
  setTimeout(() => {
    alert.show = false;
  }, showDelay);
});

// Every time feedback change
watch(feedback, () => {
  // Case new feedback alert
  if (alert.prevNum < feedback.data.length) {
    // Set an alert number
    alert.showNum++;
    const currAlertNum = alert.showNum;
    // Track alert num for condition
    alert.prevNum = feedback.data.length;
    alert.show = true;

    setTimeout(() => {
      // Exclude hidden logic if another alert is show (share same variable)
      if (currAlertNum !== alert.showNum) return;
      // Case alert fired is same after timeout
      alert.show = false;
    }, showDelay);
  }

  // Case feedback array changed but no new alert
  if (alert.prevNum > feedback.data.length)
    alert.prevNum = feedback.data.length;
});

// On each page, we are selecting tags we want to show
// Using logsStore.setTags()
const logsStore = useLogsStore();

const filters = reactive({
  tags: logsStore.tags,
});

// DATA
const logs = reactive({
  isPend: false,
  isErr: false,
  // Never modify this unless refetch
  data: [],
  current: "ui",
  maxHeight: "max-h-[90vh]",
  setup: computed(() => {
    const logsCore = [];
    const logsGlobal = [];
    if (!logs.data || logs.data.length <= 0)
      return { core: logsCore, global: logsGlobal };
    // Change to array and keep name
    const cloneData = JSON.parse(JSON.stringify(logs.data));
    const filter = getLogsByFilter(cloneData, filters);

    filter.forEach((log) => {
      if (!log.isMatchFilter) return;
      logsGlobal.push(log);
      if (log.method.toLowerCase() === "core") logsCore.push(log);
    });

    return { core: logsCore, global: logsGlobal };
  }),
});

async function getLogs() {
  await fetchAPI("/api/actions", "GET", null, logs, null);
}

onMounted(() => {
  getLogs();
  setInterval(() => {
    getLogs();
  }, 10000);
  // Change logs height to fit screen
  if (window.innerHeight >= 780) logs.maxHeight = "max-h-[90vh]";
  if (window.innerHeight < 780 && window.innerHeight >= 567)
    logs.maxHeight = "max-h-[70vh]";
  if (window.innerHeight < 567 && window.innerHeight >= 490)
    logs.maxHeight = "max-h-[65vh]";
  if (window.innerHeight < 490) logs.maxHeight = "max-h-[60vh]";
});
</script>

<template>
  <div
    class="flex justify-center fixed right-0 bottom-0 w-full sm:max-w-[300px] z-[1000]"
  >
    <FeedbackAlert
      v-if="alert.show && feedback.data.length > 0"
      :type="feedback.data[feedback.data.length - 1].type"
      :id="feedback.data[feedback.data.length - 1].id"
      :status="feedback.data[feedback.data.length - 1].status"
      :message="feedback.data[feedback.data.length - 1].message"
      @close="alert.show = false"
    />
  </div>

  <!-- float button-->
  <div
    class="group group-hover hover:brightness-75 dark:hover:brightness-105 fixed top-2 sm:top-3 right-20 sm:right-24 xl:right-24 z-990"
  >
    <button
      @click="dropdown.isOpen = dropdown.isOpen ? false : true"
      class="transition scale-90 sm:scale-100 dark:brightness-95 p-3 text-xl bg-white shadow-sm cursor-pointer rounded-circle text-slate-700"
    >
      <span class="sr-only">{{ $t("dashboard.actions.open_button") }}</span>
      <svg
        class="pointer-events-none fill-yellow-500 -translate-y-0.4 h-6 w-6"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 448 512"
      >
        <path
          d="M224 0c-17.7 0-32 14.3-32 32V51.2C119 66 64 130.6 64 208v18.8c0 47-17.3 92.4-48.5 127.6l-7.4 8.3c-8.4 9.4-10.4 22.9-5.3 34.4S19.4 416 32 416H416c12.6 0 24-7.4 29.2-18.9s3.1-25-5.3-34.4l-7.4-8.3C401.3 319.2 384 273.9 384 226.8V208c0-77.4-55-142-128-156.8V32c0-17.7-14.3-32-32-32zm45.3 493.3c12-12 18.7-28.3 18.7-45.3H224 160c0 17 6.7 33.3 18.7 45.3s28.3 18.7 45.3 18.7s33.3-6.7 45.3-18.7z"
        />
      </svg>
    </button>
    <div
      class="pointer-events-none dark:brightness-95 px-2 translate-x-2 bottom-0 right-0 absolute rounded-full bg-white"
    >
      <p class="mb-0 text-sm text-bold text-red-500">
        {{ feedback.data.length }}
      </p>
    </div>
  </div>
  <!-- end float button-->

  <!-- right sidebar -->
  <aside
    :class="[dropdown.isOpen ? '' : 'translate-x-90']"
    class="-right-0 transition z-sticky dark:bg-slate-850 dark:brightness-110 shadow-3xl max-w-full w-90 ease fixed top-0 left-auto flex h-full min-w-0 flex-col break-words rounded-none border-0 bg-white bg-clip-border px-0.5"
  >
    <!-- close btn-->
    <button
      class="absolute h-5 w-5 top-4 right-4"
      @click="dropdown.isOpen = false"
    >
      <span class="sr-only">{{ $t("dashboard.actions.open_button") }}</span>
      <svg
        class="cursor-pointer fill-gray-600 dark:fill-gray-300 dark:opacity-80"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 320 512"
      >
        <path
          d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
        />
      </svg>
    </button>
    <!-- close btn-->

    <!-- header -->
    <div class="px-6 pt-4 pb-0 mb-0 border-b-0 rounded-t-2xl">
      <div class="float-left">
        <h5 class="uppercase mt-4 mb-1 dark:text-white font-bold">
          {{ $t("dashboard.actions.title") }}
        </h5>
        <p class="capitalize-first dark:text-white dark:opacity-80 mb-0">
          {{ $t("dashboard.actions.subtitle") }}
        </p>
        <TablistBase
          @tab="(v) => (logs.current = v)"
          :current="logs.current"
          :items="[
            { text: $t('dashboard.actions.tabs.ui'), tag: 'ui' },
            { text: $t('dashboard.actions.tabs.core'), tag: 'core' },
            { text: $t('dashboard.actions.tabs.global'), tag: 'global' },
          ]"
        />
      </div>
      <!-- close button -->
      <div class="float-right mt-6">
        <button
          data-flash-sidebar-close
          class="inline-block p-0 mb-4 text-sm font-bold leading-normal text-center uppercase align-middle transition-all ease-in bg-transparent border-0 rounded-lg shadow-none cursor-pointer hover:-translate-y-px tracking-tight-rem bg-150 bg-x-25 active:opacity-85 dark:text-white text-slate-700"
        >
          <span class="sr-only">{{ $t("dashboard.actions.open_button") }}</span>

          <i class="fa fa-close"></i>
        </button>
      </div>
      <!-- end close button -->
    </div>
    <!-- end header -->

    <!-- own feedback -->
    <div
      role="tabpanel"
      :aria-hidden="logs.current === 'ui' ? 'false' : 'true'"
      :class="[logs.current === 'ui' ? 'flex' : 'hidden']"
      class="flex flex-col justify-start items-center h-full m-2 overflow-y-auto"
    >
      <FeedbackAlert
        v-for="(item, id) in feedback.data"
        :type="item.type"
        :id="item.id"
        :status="item.status"
        :message="item.message"
        @close="feedback.removeFeedback(item.id)"
      />
    </div>
    <!-- end own feedback  -->
    <div
      role="tabpanel"
      :aria-hidden="logs.current === 'core' ? 'false' : 'true'"
      :class="[logs.current === 'core' ? 'flex' : 'hidden']"
      class="flex flex-col justify-start items-center h-full m-2 overflow-y-auto"
    >
      <FeedbackLogs
        v-for="(item, id) in logs.setup.core"
        :type="item.type"
        :id="`core-${id}`"
        :title="item.title"
        :method="item.method"
        :apiMethod="item.api_method"
        :status="item.status"
        :description="item.description"
        :date="item.date"
      />
    </div>
    <div
      role="tabpanel"
      :aria-hidden="logs.current === 'global' ? 'false' : 'true'"
      :class="[logs.current === 'global' ? 'flex' : 'hidden']"
      class="flex-col justify-start items-center h-full m-2 overflow-y-auto"
    >
      <FeedbackLogs
        v-for="(item, id) in logs.setup.global"
        :type="item.type"
        :id="`global-${id}`"
        :title="item.title"
        :method="item.method"
        :apiMethod="item.api_method"
        :status="item.status"
        :description="item.description"
        :date="item.date"
      />
    </div>
  </aside>
  <!-- end right sidebar -->
</template>
