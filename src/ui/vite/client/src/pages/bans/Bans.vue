<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import BansTabs from "@components/Bans/Tabs.vue";
import BansAdd from "@components/Bans/Add.vue";
import BansList from "@components/Bans/List.vue";
import { reactive, computed, onMounted } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";

const feedbackStore = useFeedbackStore();

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  ipName: "",
  reason: "",
  dateMin: "",
  dateMax: "",
});


const instances = reactive({
  isPend: false,
  isErr: false,
  data: [],
  total : computed(() => {return instances.data.length}),
  hostnames : computed(()=> {
    if(instances.data.length === 0) return [];
    const hosts = [];
    instances.data.forEach(instance => {
      hosts.push(instance['hostname'])
    })
    return hosts;
  })
})

async function getInstances() {
  await fetchAPI(
    "/api/instances",
    "GET",
    null,
    instances,
    feedbackStore.addFeedback
  );
}

const bans = reactive({
  isPend: false,
  isErr: false,
  total : "",
  reasonList: ['all'], // Based on reasons find on fetch
  hostnames: [], // Only hostnames with retrieve ip ban
  setup: computed(()=> {
    if(instances.hostnames.length === 0) return [];
    // Fetch all instances bans    
    const promises = [];
    for (let i = 0; i < instances.hostnames.length; i++) {
      const hostname = instances.hostnames[i];
      promises.push(getHostBan(hostname));
    }
    
    // When all promises fulfill, setup data
    let bansList = [];
    Promise.all(promises).then((instances) => {
      let count = 0;
      const instNum = instances.length;
      // Loop on instances
      instances.forEach(fetchData => {
        // Case didn't retrieve ip list
        if(fetchData.type === 'error') return count++;;

        const banIps = fetchData.data;
      })
      // Case no instances data
      if(count === instNum) return [];

      bansList = values;
    })
    return bansList;
  })
});

async function getHostBan(hostname) {
  const data = {
    isPend: false,
    isErr: false,
    data: []
  }
  return await fetchAPI(
    `/api/instances/${hostname}/bans`,
    "POST",
    null,
    data,
    feedbackStore.addFeedback
  );
}


onMounted(async () => {
  await getInstances();
});

const tab = reactive({
  current : 'list'
})
</script>

<template>
  <Dashboard>
    <CardBase
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      label="info"
    >
      <CardItemList
        :items="[
          { label: 'instances total', value: instances.total },
          { label: 'ip bans total', value: bans.total },
        ]"
      />
    </CardBase>
    <CardBase
      label="ban list filter"
      class="z-[100] col-span-12 md:col-span-8 lg:col-span-6 2xl:col-span-5 3xl:col-span-4 grid grid-cols-12 relative"
    >
      <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6"
        label="Search ip"
        name="ipName"
      >
        <SettingsInput
          @inp="(v) => (filters.ipName = v)"
          :settings="{
            id: 'ipName',
            type: 'text',
            value: '',
            placeholder: '127.0.0.1',
          }"
        />
      </SettingsLayout>
      <SettingsLayout class="sm:col-span-6" label="Select reason" name="reason">
        <SettingsSelect
          @inp="
            (v) =>
              (filters.reason =
                v === 'all' ? 'all' : v )
          "
          :settings="{
            id: 'reason',
            value: 'all',
            values: bans.reasonList,
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase
    class="max-w-[1100px] col-span-12 overflow-y-hidden min-h-[400px]"
    label="ACTIONS"
    >
      <BansTabs @tab="(v) => tab.current = v" />
          <BansList :class="[tab.current === 'list' ? true : 'hidden']"  />
          <BansAdd :class="[tab.current === 'add' ? true : 'hidden']"  />
    </CardBase>
  </Dashboard>
</template>
