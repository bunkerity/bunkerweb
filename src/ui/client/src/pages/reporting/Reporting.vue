<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import ListBase from "@components/List/Base.vue";
import ReportingItems from "@components/Reporting/Items.vue";
import ApiState from "@components/Api/State.vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { reactive, computed, onMounted, watch } from "vue";
import { getReportsByFilter, getSelectList } from "@utils/reporting.js";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";

// Refresh when related btn is clicked
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  getReports();
});

const logsStore = useLogsStore();
logsStore.setTags(["reporting"]);

const feedbackStore = useFeedbackStore();

const positions = [
  "col-span-1",
  "col-span-1",
  "col-span-1",
  "col-span-1",
  "col-span-2",
  "col-span-1",
  "col-span-2",
  "col-span-1",
  "col-span-2",
];

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  search: "",
  country: "all",
  method: "all",
  status: "all",
  reason: "all",
});

// Plugins data to render components
const reports = reactive({
  isPend: false,
  isErr: false,
  // Never modify this unless refetch
  data: [],
  total: computed(() => Object.keys(reports.data).length),
  methodList: ["all"],
  countryList: ["all"],
  reasonList: ["all"],
  statusList: ["all"],
  setup: computed(() => {
    if (!reports.data || reports.data.length <= 0) return [];
    // Change to array and keep name
    const cloneData = JSON.parse(JSON.stringify(reports.data));

    // Filter data to display
    const filter = getReportsByFilter(cloneData, filters);

    // Get select list values
    const selects = ["country", "method", "reason", "status"];

    selects.forEach((selectName) => {
      // Get all values and store them
      const list = getSelectList(["all"], filter, selectName);
      reports[`${selectName}List`] = list;
      // Check that current value is in list, if not set to "all"
      filters[selectName] =
        list.indexOf(filters[selectName]) === -1 ? "all" : filters[selectName];
    });

    return filter;
  }),
});

async function getReports() {
  await fetchAPI(
    "/api/reports",
    "GET",
    null,
    reports,
    feedbackStore.addFeedback
  );
}

onMounted(() => {
  getReports();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="reports.isErr"
      :isPend="reports.isPend"
      :textState="{
        isPend: $t('api_pending', { name: $t('dashboard_reporting') }),
        isErr: $t('api_error', { name: $t('dashboard_reporting') }),
      }"
    />
    <CardBase
      v-if="!reports.isErr && !reports.isPend"
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      :label="$t('dashboard_info')"
    >
      <CardItemList
        :items="[
          { label: $t('reporting_total'), value: reports.total },
          {
            label: $t('reporting_country'),
            value: reports.countryList.length - 1,
          },
          {
            label: $t('reporting_reason'),
            value: reports.reasonList.length - 1,
          },
        ]"
      />
    </CardBase>
    <CardBase
      v-if="!reports.isErr && !reports.isPend"
      class="z-10 h-fit col-span-12 md:col-span-8 xl:col-span-8 2xl:col-span-5 3xl:col-span-4"
      :label="$t('dashboard_filter')"
    >
      <SettingsLayout
        class="sm:col-span-6"
        :label="$t('reporting_filter_search')"
        name="keyword"
      >
        <SettingsInput
          @inp="(v) => (filters.search = v)"
          :settings="{
            id: 'keyword',
            type: 'text',
            value: '',
            placeholder: $t('reporting_filter_search_placeholder'),
          }"
        />
      </SettingsLayout>

      <SettingsLayout
        class="sm:col-span-6"
        :label="$t('reporting_filter_method')"
        name="reporting-method"
        :key="reports.methodList.length"
      >
        <SettingsSelect
          @inp="(v) => (filters.method = v)"
          :settings="{
            id: 'reporting-method',
            value: filters.method,
            values: reports.methodList,
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="sm:col-span-6"
        :label="$t('reporting_filter_country')"
        name="reporting-country"
        :key="reports.countryList.length"
      >
        <SettingsSelect
          @inp="(v) => (filters.country = v)"
          :settings="{
            id: 'reporting-country',
            value: filters.country,
            values: reports.countryList,
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="sm:col-span-6"
        :label="$t('reporting_filter_status')"
        name="reporting-status"
        :key="reports.statusList.length"
      >
        <SettingsSelect
          @inp="(v) => (filters.status = v)"
          :settings="{
            id: 'reporting-status',
            value: filters.status,
            values: reports.statusList,
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="sm:col-span-6"
        :label="$t('reporting_filter_reason')"
        name="reporting-reason"
        :key="reports.reasonList.length"
      >
        <SettingsSelect
          @inp="(v) => (filters.reason = v)"
          :settings="{
            id: 'reporting-reason',
            value: filters.reason,
            values: reports.reasonList,
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase
      v-if="!reports.isErr && !reports.isPend && reports.length > 0"
      class="col-span-12 overflow-x-auto overflow-y-hidden"
      :label="$t('dashboard_reporting')"
    >
      <div class="col-span-12 overflow-x-auto grid grid-cols-12">
        <ListBase
          class="min-w-[1100px] col-span-12"
          :header="[
            $t('reporting_header_date'),
            $t('reporting_header_ip'),
            $t('reporting_header_country'),
            $t('reporting_header_method'),
            $t('reporting_header_url'),
            $t('reporting_header_code'),
            $t('reporting_header_user_agent'),
            $t('reporting_header_reason'),
            $t('reporting_header_data'),
          ]"
          :positions="positions"
        >
          <ReportingItems
            :summary="$t('reporting_table_summary')"
            :positions="positions"
            :items="reports.setup"
          >
          </ReportingItems>
        </ListBase>
      </div>
    </CardBase>
  </Dashboard>
</template>
