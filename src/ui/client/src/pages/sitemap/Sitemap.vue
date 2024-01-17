<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import CardBase from "@components/Card/Base.vue";
import { reactive, computed, onMounted, watch } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";
import { pluginI18n } from "@utils/plugins.js";
import { useI18n } from "vue-i18n";
const { locale, fallbackLocale } = useI18n();
// Refresh when related btn is clicked
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  getVersion();
  getInstances();
  getConf();
});

const logsStore = useLogsStore();
logsStore.setTags(["all"]);

const feedbackStore = useFeedbackStore();

const basePages = [
  { name: "account", path: "/account" },
  { name: "home", path: "/home" },
  {
    name: "instances",
    path: "/instances",
  },

  {
    name: "global_config",
    path: "/global-config",
  },
  {
    name: "services",
    path: "/services",
  },
  {
    name: "configs",
    path: "/configs",
  },
  {
    name: "plugins",
    path: "/plugins",
  },
  { name: "jobs", path: "/jobs" },
  { name: "bans", path: "/bans" },
  {
    name: "actions",
    path: "/actions",
  },
];

// Plugins data to render components
const plugins = reactive({
  isPend: false,
  isErr: false,
  // Never modify this unless refetch
  data: [],
  total: computed(() => plugins.data.length),

  // This run every time reactive data changed (plugin.base or filters)
  setup: computed(() => {
    if (plugins.isPend || plugins.isErr || plugins.data.length === 0) return [];

    // Filter data to display
    const cloneBase = JSON.parse(JSON.stringify(plugins.data));
    // translate
    pluginI18n(cloneBase, locale.value, fallbackLocale.value);

    // get pages
    const pluginPages = [];
    cloneBase.forEach((plugin) => {
      if (plugin["page"]) {
        pluginPages.push({ name: plugin });
      }
    });

    return pluginPages;
  }),
});

async function getPlugins() {
  await fetchAPI(
    "/api/plugins",
    "GET",
    null,
    plugins,
    feedbackStore.addFeedback,
  );
}

onMounted(() => {
  getPlugins();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-span-6 2xl:col-span-4"
      :isErr="plugins.isErr"
      :isPend="plugins.isPend"
      :textState="{
        isPend: $t('api_pending', { name: $t('dashboard_plugins') }),
        isErr: $t('api_error', { name: $t('dashboard_plugins') }),
      }"
    />
    <CardBase
      class="h-fit col-span-12 max-w-[800px]"
      :label="$t('dashboard_sitemap')"
    >
      <div class="col-span-12">
        <h2>{{ $t("dashboard_default") }}</h2>
        <ul>
          <li v-for="(page, id) in basePages">
            <a :tabindex="id + 1" :href="page.path">
              {{ $t(`dashboard_${page.name}`) }}
            </a>
          </li>
        </ul>
      </div>
      <div class="col-span-12" v-if="plugins.setup.length !== 0">
        <h2>{{ $t("dashboard_plugins") }}</h2>
        <ul>
          <li v-for="(page, id) in plugins.setup">
            <a :tabindex="basePages.length + id" :href="page.path">
              {{ page.name }}
            </a>
          </li>
        </ul>
      </div>
    </CardBase>
  </Dashboard>
</template>
