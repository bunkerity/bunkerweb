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
import { reactive, computed, onMounted, watch } from "vue";
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
  hostnames : [],
  total : computed(() => {return instances.hostnames.length}),
})

const bans = reactive({
  data: [],
  total : "",
  reasonList: ['all'], // Based on reasons find on fetch
  bansList : [] // Format {hostname : str, data : Array}
});

async function getData() {
  const getInstances = await fetchAPI(
    "/api/instances",
    "GET",
    null,
    instances,
    feedbackStore.addFeedback,
  );
  const hostnames = await getHostFromInst();
  return await getBansFromInst(hostnames);
}

async function getHostFromInst() {
  const hosts = [];
    instances.data.forEach(instance => {
      hosts.push(instance['hostname'])
  })
  instances.hostnames = hosts;
  return hosts;
}

async function getBansFromInst(hostnames) {
  if(hostnames.length === 0) return bans.data = [];
    // Fetch all instances bans    
    const promises = [];
    for (let i = 0; i < hostnames.length; i++) {
      const hostname = hostnames[i];
      promises.push(getHostBan(hostname));
    }

    // When all promises fulfill, 
    const bansList = [];
    Promise.all(promises).then((instances) => {
        instances.forEach((instance, id) => {
          bansList.push({hostname : hostnames[id], data: JSON.parse(instance.data) || []})
        });

        console.log(bansList)

        // Create a global instance that regroup every ip
        // And remove duplicate items
        // And get all reasons
        const reasons = ["all"];
        const globalInst = {hostname : "all", data : []};
        for (let i = 0; i < bansList.length; i++) {
          const instData = bansList[i].data;
          instData.forEach(item => {
              // Format stamp and exp to ms
              item.date = item.date.toString().length === 10 ? +`${item.date}000` : item.date;
              item.exp = +`${item.exp}000`;
              reasons.indexOf(item.reason) === -1 ? reasons.push(item.reason) : false;
              const isItem = globalInst.data.find(globItem => {return item.ip === globItem.ip && item.reason === globItem.reason});
              console.log(item.date.toString().length)
              if(!isItem) globalInst.data.push(item)
          })
        }

        bans.bansList = bansList;
        bans.reasonList = reasons;
      })


}



async function getHostBan(hostname) {
  const data = {
    isPend: false,
    isErr: false,
    data: [],
  };
  return await fetchAPI(
    `/api/instances/${hostname}/bans`,
    "POST",
    null,
    data,
    feedbackStore.addFeedback,
  );
}


onMounted(() => {
  getData();
});

const tab = reactive({
  current: "list",
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
          @inp="(v) => (filters.reason = v === 'all' ? 'all' : v)"
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
      <BansList :items="bans.bansList" :class="[tab.current === 'list' ? true : 'hidden']"  />
      <BansAdd @addBans="getData()" :class="[tab.current === 'add' ? true : 'hidden']"  />
    </CardBase>
  </Dashboard>
</template>
