<script setup>
import FeedbackAlert from "@components/Feedback/Alert.vue";
import FeedbackLogs from "@components/Feedback/Logs.vue";
import { useFeedbackStore } from "@store/global.js";
import { reactive, watch, onMounted, computed } from "vue";
import TablistBase from "@components/Tablist/Base.vue";
import { getLogsByFilter } from "@utils/logs.js";
import { fetchAPI } from "@utils/api.js";
import { useLogsStore } from "@store/logs.js";
import { useBannerStore } from "@store/global.js";

// Handle feedback history panel
const dropdown = reactive({
  isOpen: false,
});

// Share feedback store
// Get changes from another component and display alert
const feedback = useFeedbackStore();

// Use to update position when banner is visible or not
const bannerStore = useBannerStore();

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
    :class="[bannerStore.isBanner ? 'banner' : 'no-banner']"
    class="feedback-float-btn-container group group-hover"
  >
    <button
      aria-controls="feedback-sidebar group group-hover"
      :aria-expanded="dropdown.isOpen ? 'true' : 'false'"
      @click="dropdown.isOpen = dropdown.isOpen ? false : true"
      class="feedback-float-btn"
    >
      <span class="sr-only">{{ $t("dashboard_open_sidebar") }}</span>
      <svg
        class="feedback-float-btn-svg"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 448 512"
      >
        <path
          d="M224 0c-17.7 0-32 14.3-32 32V51.2C119 66 64 130.6 64 208v18.8c0 47-17.3 92.4-48.5 127.6l-7.4 8.3c-8.4 9.4-10.4 22.9-5.3 34.4S19.4 416 32 416H416c12.6 0 24-7.4 29.2-18.9s3.1-25-5.3-34.4l-7.4-8.3C401.3 319.2 384 273.9 384 226.8V208c0-77.4-55-142-128-156.8V32c0-17.7-14.3-32-32-32zm45.3 493.3c12-12 18.7-28.3 18.7-45.3H224 160c0 17 6.7 33.3 18.7 45.3s28.3 18.7 45.3 18.7s33.3-6.7 45.3-18.7z"
        />
      </svg>
    </button>
    <div class="feedback-float-btn-text-container">
      <p class="feedback-float-btn-text">
        {{ feedback.data.length }}
      </p>
    </div>
  </div>
  <!-- end float button-->

  <!-- right sidebar -->
  <aside
    id="feedback-sidebar"
    :aria-hidden="dropdown.isOpen ? 'false' : 'true'"
    :class="[dropdown.isOpen ? '' : 'translate-x-90']"
    class="feedback-sidebar"
  >
    <!-- close btn-->
    <button
      aria-controls="feedback-sidebar"
      :aria-expanded="dropdown.isOpen ? 'true' : 'false'"
      class="feedback-header-close-btn"
      @click="dropdown.isOpen = false"
    >
      <span class="sr-only">{{ $t("dashboard_close_sidebar") }}</span>
      <svg
        @click="dropdown.isOpen = false"
        class="feedback-header-close-btn-svg"
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
    <div class="feedback-header">
      <div class="float-left">
        <h5 class="feedback-header-title">
          {{ $t("dashboard_actions_title") }}
        </h5>
        <p class="feedback-header-subtitle">
          {{ $t("dashboard_actions_subtitle") }}
        </p>
        <TablistBase
          @tab="(v) => (logs.current = v)"
          :current="logs.current"
          :items="[
            { text: $t('dashboard_ui'), tag: 'ui' },
            { text: $t('dashboard_core'), tag: 'core' },
            { text: $t('dashboard_global'), tag: 'global' },
          ]"
        />
      </div>
    </div>
    <!-- end header -->

    <!-- own feedback -->
    <div
      role="tabpanel"
      :aria-hidden="logs.current === 'ui' ? 'false' : 'true'"
      :class="[logs.current === 'ui' ? 'flex' : 'hidden']"
      class="feedback-panel"
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
      class="feedback-panel"
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
      class="feedback-panel"
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
