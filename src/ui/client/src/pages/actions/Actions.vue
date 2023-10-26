<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import ListBase from "@components/List/Base.vue";
import ActionsItems from "@components/Actions/Items.vue";
import ApiState from "@components/Api/State.vue";

import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { reactive, computed, onMounted } from "vue";
import { getActionsByFilter } from "@utils/actions.js";

const feedbackStore = useFeedbackStore();

const positions = ["col-span-2", "col-span-3", "col-span-4", "col-span-3"];

const header = ["Method", "Title", "Description", "Date"];

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  name: "",
  method: "all",
});

// Plugins data to render components
const actions = reactive({
  isPend: false,
  isErr: false,
  // Never modify this unless refetch
  data: [],
  total: computed(() => Object.keys(actions.data).length),
  ui: 0,
  autoconf: 0,
  methodList: ["all"],
  setup: computed(() => {
    // Change to array and keep name
    const cloneData = JSON.parse(JSON.stringify(actions.data));
    const dataArr = [];
    for (const [key, value] of Object.entries(cloneData)) {
      dataArr.push({ [key]: cloneData[key] });
    }

    // Filter data to display
    const filter = getActionsByFilter(dataArr, filters);
    return filter;
  }),
});

async function getActions() {
  await fetchAPI("/api/jobs", "GET", null, jobs, feedbackStore.addFeedback);
}

onMounted(() => {
  getActions();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="actions.isErr"
      :isPend="actions.isPend"
      :textState="{
        isPend: 'Try retrieve actions',
        isErr: 'Error retrieving actions',
      }"
    />
    <CardBase
      v-if="!actions.isErr && !actions.isPend"
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      label="info"
    >
      <CardItemList
        :items="[
          { label: 'actions total', value: actions.total },
          { label: 'actions ui', value: actions.ui },
          { label: 'actions autoconf', value: actions.autoconf },
        ]"
      />
    </CardBase>
    <CardBase
      v-if="!actions.isErr && !actions.isPend"
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
        label="Method"
        name="actions-method"
      >
        <SettingsSelect
          @inp="(v) => (filters.method = v)"
          :settings="{
            id: 'actions-method',
            value: filters.method,
            values: actions.methodList,
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase
      v-if="!actions.isErr && !actions.isPend"
      class="col-span-12 overflow-x-auto overflow-y-hidden"
      label="jobs"
    >
      <ListBase
        class="min-w-[1100px] col-span-12"
        :header="header"
        :positions="positions"
      >
        <ActionsItems :positions="positions" :items="jobs.setup">
        </ActionsItems>
      </ListBase>
    </CardBase>
  </Dashboard>
</template>
