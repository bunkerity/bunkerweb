<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import HomeCardStructure from "@components/Home/Card/Structure.vue";
import HomeCardSvgVersion from "@components/Home/Card/Svg/Version.vue";
import HomeCardSvgInstances from "@components/Home/Card/Svg/Instances.vue";
import HomeCardSvgServices from "@components/Home/Card/Svg/Services.vue";
import HomeCardSvgPlugins from "@components/Home/Card/Svg/Plugins.vue";
import ApiState from "@components/Api/State.vue";
import { reactive, computed, onMounted, watch } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";

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

const instances = reactive({
  isPend: false,
  isErr: false,
  data: [],
  count: computed(() => instances.data.length),
  up: computed(() =>
    instances.data.filter((item) => item.status === "up").length.toString(),
  ),
  down: computed(() =>
    instances.data.filter((item) => item.status !== "up").length.toString(),
  ),
});

async function getInstances() {
  await fetchAPI(
    "/api/instances",
    "GET",
    null,
    instances,
    feedbackStore.addFeedback,
  );
}

const version = reactive({
  isPend: false,
  isErr: false,
  data: "",
  num: computed(() => version.data),
  latest: "0",
  isLatest: computed(() => {
    return version.latest.includes(version.num) ? true : false;
  }),
});

async function getVersion() {
  await fetchAPI(
    "/api/version",
    "GET",
    null,
    version,
    feedbackStore.addFeedback,
  );
  // Get latest version from github
  await fetch("https://api.github.com/repos/bunkerity/bunkerweb/tags")
    .then((res) => {
      return res.json();
    })
    .then((res) => {
      if (res.length <= 0) return;

      version.latest = res[0]["name"] || null;
    });
}

// Plugins data to render components
const plugins = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  num: computed(() => plugins.data.length),
  internal: computed(
    () => plugins.data.filter((item) => item["external"] === false).length,
  ),
  external: computed(
    () => plugins.data.filter((item) => item["external"] === true).length,
  ),
  services: computed(() => {
    if (
      plugins.isErr ||
      plugins.isPend ||
      !plugins.data ||
      plugins.data.length === 0 ||
      conf.isErr ||
      conf.isPend ||
      !conf.data ||
      conf.data.length === 0
    ) {
      return [];
    }
    // Get only services custom conf
    const cloneServConf = JSON.parse(JSON.stringify(conf.data["services"]));
    return cloneServConf;
  }),
  servicesNum: computed(() => Object.keys(plugins.services).length),
});

const conf = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  services: computed(() => {
    Object.keys(conf.data.services).length;
  }),
});

async function getConf() {
  conf.isPend = true;
  plugins.isPend = true;
  await fetchAPI(
    "/api/config?methods=1&new_format=1",
    "GET",
    null,
    conf,
    feedbackStore.addFeedback,
  );
  await fetchAPI(
    "/api/plugins",
    "GET",
    null,
    plugins,
    feedbackStore.addFeedback,
  );
}

onMounted(() => {
  getVersion();
  getInstances();
  getConf();
});
</script>

<template>
  <Dashboard>
    <!-- version -->
    <ApiState
      class="col-span-12 md:col-span-6 2xl:col-span-4"
      :isErr="version.isErr"
      :isPend="version.isPend"
      :textState="{
        isPend: 'Try retrieve version',
        isErr: 'Error retrieving version',
      }"
    />
    <HomeCardStructure
      v-if="!version.isPend && !version.isErr"
      :href="'#'"
      :name="'version'"
      :count="version.num"
      :detailArr="[
        {
          text: version.isLatest ? 'Latest version' : 'is latest version',
          num: version.isLatest ? '' : version.latest,
          textClass: version.isLatest ? 'text-green-500' : 'text-yellow-500',
          numClass: version.isLatest ? 'text-green-500' : 'text-yellow-500',
        },
      ]"
    >
      <HomeCardSvgVersion />
    </HomeCardStructure>
    <!-- end version -->

    <!-- instances -->
    <ApiState
      class="col-span-12 md:col-span-6 2xl:col-span-4"
      :isErr="instances.isErr"
      :isPend="instances.isPend"
      :textState="{
        isPend: 'Try retrieve instances',
        isErr: 'Error retrieving instances',
      }"
    />
    <HomeCardStructure
      v-if="!instances.isPend && !instances.isErr && instances.data"
      :href="'/admin/instances'"
      :name="'instances'"
      :count="instances.count || '0'"
      :detailArr="[
        {
          text: 'up',
          num: instances.up,
          textClass: 'text-green-500',
          numClass: 'text-green-500',
        },
        {
          text: 'stop',
          num: instances.down,
          textClass: 'text-red-500',
          numClass: 'text-red-500',
        },
      ]"
    >
      <HomeCardSvgInstances />
    </HomeCardStructure>
    <!-- end instances -->

    <!-- services -->
    <ApiState
      class="col-span-12 md:col-span-6 2xl:col-span-4"
      :isErr="plugins.isErr"
      :isPend="plugins.isPend"
      :textState="{
        isPend: 'Try retrieve services',
        isErr: 'Error retrieving services',
      }"
    />
    <HomeCardStructure
      v-if="!plugins.isPend && !plugins.isErr && plugins.data.length > 0"
      :href="'/admin/services'"
      :name="'services'"
      :count="plugins.servicesNum || '0'"
      :detailArr="[
        {
          text: 'ui,',
          num: '',
          textClass: 'text-sky-500',
          numClass: 'text-sky-500',
        },
        {
          text: 'autoconf',
          num: '',
          textClass: 'text-sky-500',
          numClass: 'text-sky-500',
        },
      ]"
    >
      <HomeCardSvgServices />
    </HomeCardStructure>
    <!-- end services-->
    <!-- plugins -->
    <ApiState
      class="col-span-12 md:col-span-6 2xl:col-span-4"
      :isErr="conf.isErr"
      :isPend="conf.isPend"
      :textState="{
        isPend: 'Try retrieve plugins',
        isErr: 'Error retrieving plugins',
      }"
    />
    <HomeCardStructure
      v-if="!conf.isPend && !conf.isErr"
      :href="'/admin/plugins'"
      :name="'plugins'"
      :count="plugins.num || '0'"
      :detailArr="[
        {
          text: 'internal,',
          num: plugins.internal || '0',
          textClass: 'text-sky-500',
          numClass: 'text-sky-500',
        },
        {
          text: 'external',
          num: plugins.external || '0',
          textClass: 'text-sky-500',
          numClass: 'text-sky-500',
        },
      ]"
    >
      <HomeCardSvgPlugins />
    </HomeCardStructure>
    <!-- end plugins-->
  </Dashboard>
</template>
