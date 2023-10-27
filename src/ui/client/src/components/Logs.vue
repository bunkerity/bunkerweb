<script setup>
import { onMounted, reactive, computed } from "vue";
import TablistBase from "@components/Tablist/Base.vue";
import ListItem from "@components/List/Item.vue";
import { getLogsByFilter } from "@utils/logs.js";
import { fetchAPI } from "@utils/api.js";
import { useLogsStore } from "@store/logs.js";

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
    if (!logs.data || logs.data.length <= 0) return [];
    // Change to array and keep name
    const cloneData = JSON.parse(JSON.stringify(logs.data));
    const filter = getLogsByFilter(cloneData, filters);
    console.log(filter);

    const logUI = [];
    const logCore = [];
    filter.forEach((log) => {
      if (!log.isMatchFilter) return;
      if (log.method.toLowerCase() === "core") logCore.push(log);
      if (log.method.toLowerCase() === "ui") logUI.push(log);
    });

    return { ui: logUI, core: logCore };
  }),
});

async function getLogs() {
  await fetchAPI("/api/actions", "GET", null, logs, null);
}

onMounted(() => {
  getLogs();
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
  <!-- float button-->
  <button
    :aria-checked="logs.isActive ? 'true' : 'false'"
    type="button"
    @click="logs.isActive = logs.isActive ? false : true"
    class="logs-float-btn"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke-width="1.5"
      stroke="currentColor"
      class="stroke-gray-700 h-6 w-6 scale-[1.3]"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z"
      />
    </svg>
  </button>
  <!-- end float button-->

  <!-- right sidebar -->
  <aside
    :aria-expanded="logs.isActive ? 'true' : 'false'"
    :aria-hidden="logs.isActive ? 'false' : 'true'"
    :class="[logs.isActive ? '' : 'translate-x-[22.5rem]', 'news-sidebar']"
  >
    <!-- close btn-->
    <svg
      type="button"
      @click="logs.isActive = false"
      class="news-close-btn"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 320 512"
    >
      <path
        d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
      />
    </svg>
    <!-- close btn-->

    <!-- header -->
    <div class="news-sidebar-header">
      <div class="w-full">
        <h5 class="news-sidebar-title">ACTIONS</h5>
        <p class="news-sidebar-subtitle mb-4">Related to page tags</p>
        <TablistBase
          @tab="(v) => (logs.current = v)"
          :current="logs.current"
          :items="[
            { text: 'UI', tag: 'ui' },
            { text: 'core', tag: 'core' },
          ]"
        />
      </div>
      <ul
        :class="[logs.maxHeight]"
        class="overflow-auto"
        v-if="logs.current === 'ui'"
      >
        <ListItem v-for="item in logs.setup.ui">
          <div class="list-content-item-wrap px-2">
            <div class="col-span-12">
              <div class="flex justify-between">
                <strong class="mb-0.5 font-bold">{{ item.title }}</strong>
                <div class="flex mb-0.5">
                  <p class="mb-0.5">{{ item.method.toUpperCase() }}</p>
                  <span class="mb-0.5">|</span>
                  <p class="mb-0.5">{{ item.api_method }}</p>
                </div>
              </div>
              <p class="mb-1.5">{{ item.description }}</p>
              <div class="flex items-center justify-end">
                <p class="text-right text-xs italic mb-0">
                  {{ item.date }}
                </p>
              </div>
            </div>
          </div>
        </ListItem>
      </ul>
      <ul
        :class="[logs.maxHeight]"
        class="overflow-auto"
        v-if="logs.current === 'core'"
      >
        <ListItem v-for="item in logs.setup.core">
          <div class="list-content-item-wrap px-2">
            <div class="col-span-12">
              <div class="flex justify-between">
                <strong class="mb-0.5 font-bold">{{ item.title }}</strong>
                <div class="flex mb-0.5">
                  <p class="mb-0.5">{{ item.method.toUpperCase() }}</p>
                  <span class="mb-0.5">|</span>
                  <p class="mb-0.5">{{ item.api_method }}</p>
                </div>
              </div>
              <p class="mb-1.5">{{ item.description }}</p>
              <div class="flex items-center justify-end">
                <p class="text-right text-xs italic mb-0">
                  {{ item.date }}
                </p>
              </div>
            </div>
          </div>
        </ListItem>
      </ul>
    </div>
    <!-- end header -->
  </aside>
  <!-- end right sidebar -->
</template>
