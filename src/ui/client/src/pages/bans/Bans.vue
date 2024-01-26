<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import BansModalAdd from "@components/Bans/Modal/Add.vue";
import BansButtonAdd from "@components/Bans/Button/Add.vue";
import BansList from "@components/Bans/List.vue";
import ApiState from "@components/Api/State.vue";
import { reactive, computed, onMounted, watch } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { getBansByFilter } from "@utils/bans.js";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";
import { useAddModalStore } from "@store/bans.js";
import { contentIndex } from "@utils/tabindex.js";

const addModalStore = useAddModalStore();
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  getData();
});

const logsStore = useLogsStore();
logsStore.setTags(["instance"]);

const feedbackStore = useFeedbackStore();

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  search: "",
  reason: "all",
});

const instances = reactive({
  isPend: false,
  isErr: false,
  data: [],
  hostnames: [],
  total: "null",
});

const bans = reactive({
  data: [],
  isPend: false,
  isErr: false,
  total: "null",
  reasonList: ["all"], // Based on reasons find on fetch
  bansList: [], // Format {hostname : str, data : Array}
  setup: computed(() => {
    instances.total = bans.data.length;
    if (bans.data.length === 0) return;

    // Create a global instance that regroup every ip
    // And remove duplicate items
    // And get all reasons
    const reasons = ["all"];
    const globalInst = [];
    for (let i = 0; i < bans.data.length; i++) {
      if (!Array.isArray(bans.data[i].data)) continue;
      const instBans = bans.data[i].data;
      instBans.forEach((item) => {
        reasons.indexOf(item.reason) === -1 ? reasons.push(item.reason) : false;
        const isItem = globalInst.find((globItem) => {
          return item.ip === globItem.ip && item.reason === globItem.reason;
        });
        if (!isItem) globalInst.push(item);
      });
    }
    bans.total = globalInst.length;
    bans.reasonList = reasons;
    //Filter
    const filterBans = getBansByFilter(globalInst, filters);
    return filterBans;
  }),
});

async function getData() {
  const getInstances = await fetchAPI(
    "/api/instances",
    "GET",
    null,
    instances,
    feedbackStore.addFeedback
  );
  const hostnames = await getHostFromInst();

  return await getHostFromInst();
}

async function getHostFromInst() {
  const hosts = [];
  if (!Array.isArray(instances.data)) return;

  instances.data.forEach((instance) => {
    hosts.push(instance["hostname"]);
  });
  return await setHostBan(hosts);
}

async function setHostBan(hostnames) {
  // Fetch all instances bans
  bans.isPend = true;
  bans.isErr = false;
  const promises = [];
  for (let i = 0; i < hostnames.length; i++) {
    const hostname = hostnames[i];
    promises.push(getHostBan(hostname));
  }

  const bansList = [];
  Promise.all(promises).then((instances) => {
    bans.isPend = false;
    instances.forEach((instance, id) => {
      if (instance.type === "error") bans.isErr = true;
      bansList.push({
        hostname: hostnames[id],
        data: JSON.parse(instance.data) || [],
      });
    });
    bans.data = bansList;
  });
}

async function getHostBan(hostname) {
  const data = {
    isPend: false,
    isErr: false,
    data: [],
  };
  return await fetchAPI(
    `/api/instances/${hostname}/bans?method=ui`,
    "POST",
    null,
    data,
    feedbackStore.addFeedback
  );
}

onMounted(() => {
  getData();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="instances.isErr || bans.isErr"
      :isPend="instances.isPend || bans.isPend"
      :textState="{
        isPend: $t('api_pending', { name: $t('dashboard_bans') }),
        isErr: $t('api_error', { name: $t('dashboard_bans') }),
      }"
    />

    <div
      class="col-span-12 relative flex justify-center min-w-0 break-words rounded-2xl bg-clip-border"
    >
      <BansButtonAdd
        :tabindex="addModalStore.isOpen ? '-1' : contentIndex"
        v-if="
          !instances.isErr && !instances.isPend && !bans.isPend && !bans.isErr
        "
      />
    </div>

    <CardBase
      v-if="
        !instances.isErr && !instances.isPend && !bans.isPend && !bans.isErr
      "
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      :label="$t('dashboard_info')"
    >
      <CardItemList
        :items="[
          {
            label: $t('bans_instances_total'),
            value: instances.total,
          },
          {
            label: $t('bans_ip_bans_total'),
            value: bans.total,
          },
        ]"
      />
    </CardBase>

    <CardBase
      v-if="
        !instances.isErr && !instances.isPend && !bans.isPend && !bans.isErr
      "
      :label="$t('dashboard_filter')"
      class="z-[100] col-span-12 md:col-span-8 lg:col-span-6 2xl:col-span-5 3xl:col-span-4 grid grid-cols-12 relative"
    >
      <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6"
        :label="$t('bans_filter_search_ip')"
        name="ipName"
      >
        <SettingsInput
          @inp="(v) => (filters.search = v)"
          :tabId="addModalStore.isOpen ? '-1' : contentIndex"
          :settings="{
            id: 'ipName',
            type: 'text',
            value: '',
            placeholder: $t('bans_add_ip_placeholder'),
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="sm:col-span-6"
        :label="$t('bans_filter_reason')"
        name="reason"
      >
        <SettingsSelect
          @inp="(v) => (filters.reason = v)"
          :tabId="addModalStore.isOpen ? '-1' : contentIndex"
          :settings="{
            id: 'reason',
            value: filters.reason,
            values: bans.reasonList,
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase
      class="max-w-[1200px] col-span-12 overflow-y-hidden min-h-[400px]"
      :label="$t('dashboard_bans')"
    >
      <BansList :items="bans.setup" />
    </CardBase>
    <BansModalAdd />
  </Dashboard>
</template>
