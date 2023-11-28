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
import { reactive, computed, onMounted, watch } from "vue";
import { getActionsByFilter, getSelectList } from "@utils/actions.js";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";

// Refresh when related btn is clicked
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  getActions();
});

const logsStore = useLogsStore();
logsStore.setTags(["action"]);

const feedbackStore = useFeedbackStore();

const positions = [
  "col-span-2",
  "col-span-3",
  "col-span-3",
  "col-span-3",
  "col-span-1",
];

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  search: "",
  method: "all",
  actionApi: "all",
});

// Plugins data to render components
const actions = reactive({
  isPend: false,
  isErr: false,
  // Never modify this unless refetch
  data: [],
  total: computed(() => Object.keys(actions.data).length),
  core: 0,
  ui: 0,
  methodList: ["all"],
  actionApiList: ["all"],
  setup: computed(() => {
    if (!actions.data || actions.data.length <= 0) return [];
    // Change to array and keep name
    const cloneData = JSON.parse(JSON.stringify(actions.data));

    // Filter data to display
    const filter = getActionsByFilter(cloneData, filters);

    // Get method select list
    const methodList = getSelectList(["all"], filter, "method");

    filters.method =
      methodList.indexOf(filters.method) === -1 ? "all" : filters.method;
    actions.methodList = methodList;

    // Get action api select list
    const actionApiList = getSelectList(["all"], filter, "api_method");

    filters.actionApi =
      actionApiList.indexOf(filters.actionApi) === -1
        ? "all"
        : filters.actionApi;
    actions.actionApiList = actionApiList;

    // Update info
    let countUI = 0;
    let countCore = 0;
    filter.forEach((action) => {
      if (action.method.toLowerCase() === "core") countCore++;
      if (action.method.toLowerCase() === "ui") countUI++;
    });
    actions.core = countCore;
    actions.ui = countUI;

    return filter;
  }),
});

async function getActions() {
  await fetchAPI(
    "/api/actions",
    "GET",
    null,
    actions,
    feedbackStore.addFeedback,
  );
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
        isPend: $t('actions.api.pending'),
        isErr: $t('actions.api.error'),
      }"
    />
    <CardBase
      v-if="!actions.isErr && !actions.isPend"
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      :label="$t('actions.card.info.title')"
    >
      <CardItemList
        :items="[
          { label: $t('actions.card.info.items.total'), value: actions.total },
          { label: $t('actions.card.info.items.ui'), value: actions.ui },
          { label: $t('actions.card.info.items.core'), value: actions.core },
        ]"
      />
    </CardBase>
    <CardBase
      v-if="!actions.isErr && !actions.isPend"
      class="z-10 h-fit col-span-12 md:col-span-8 xl:col-span-8 2xl:col-span-5 3xl:col-span-4"
      :label="$t('actions.card.filter.title')"
    >
      <SettingsLayout
        class="sm:col-span-6"
        :label="$t('actions.card.filter.search.label')"
        name="keyword"
      >
        <SettingsInput
          @inp="(v) => (filters.search = v)"
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
        :label="$t('actions.card.filter.method.label')"
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
      <SettingsLayout
        class="sm:col-span-6"
        :label="$t('actions.card.filter.api_method.label')"
        name="actions-action-api"
      >
        <SettingsSelect
          @inp="(v) => (filters.actionApi = v)"
          :settings="{
            id: 'actions-action-api',
            value: filters.actionApi,
            values: actions.actionApiList,
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase
      v-if="!actions.isErr && !actions.isPend"
      class="col-span-12 overflow-x-auto overflow-y-hidden"
      :label="$t('actions.card.actions.title')"
    >
      <ListBase
        class="min-w-[1100px] col-span-12"
        :header="[
          $t('actions.card.actions.header.method'),
          $t('actions.card.actions.header.title'),
          $t('actions.card.actions.header.description'),
          $t('actions.card.actions.header.date'),
          $t('actions.card.actions.header.action'),
        ]"
        :positions="positions"
      >
        <ActionsItems :positions="positions" :items="actions.setup">
        </ActionsItems>
      </ListBase>
    </CardBase>
  </Dashboard>
</template>
