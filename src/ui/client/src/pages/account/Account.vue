<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import ButtonBase from "@components/Button/Base.vue";
import CardBase from "@components/Card/Base.vue";
import CardLabel from "@components/Card/Label.vue";
import PluginStructure from "@components/Plugin/Structure.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import { reactive, computed, onMounted, watch } from "vue";
import { getMethodList, getSettingsByFilter } from "@utils/settings.js";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";
import { useI18n } from "vue-i18n";

const { locale, fallbackLocale } = useI18n();

// Refresh when related btn is clicked
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  refresh();
});

const logsStore = useLogsStore();
logsStore.setTags(["config", "plugin"]);

const config = useConfigStore();

const feedbackStore = useFeedbackStore();

// Plugins data to render components
const account = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  setup: computed(() => {
    if (account.isErr || account.isPend || !account.data) {
      return [];
    }

    return account.data;
  }),
});

const username = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  userValue: "",
  pwValue: "",
  setup: computed(() => {
    if (username.isErr || username.isPend || !username.data) {
      return [];
    }
    return username.data;
  }),
});

async function updateUsername() {
  // Case no data to send
  if (!username.value) return;

  await fetchAPI(
    "/api/database/account/username",
    "POST",
    { username: username.value, password: username.pwValue },
    username,
    feedbackStore.addFeedback
  ).then((res) => {
    if (res.status === 200) {
      refresh(false);
    }
  });
}

const pw = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  currValue: "",
  newValue: "",
  newConfirmValue: "",
  setup: computed(() => {
    if (pw.isErr || pw.isPend || !pw.data) {
      return [];
    }
    return pw.data;
  }),
});

async function updatePassword() {
  // Case no data to send
  if (!pw.currValue && !pw.newValue && !pw.newConfirmValue) return;

  await fetchAPI(
    "/api/database/account/password",
    "POST",
    {
      password: pw.currValue,
      new_password: pw.newValue,
      new_password_confirm: pw.newConfirmValue,
    },
    pw,
    feedbackStore.addFeedback
  ).then((res) => {
    if (res.status === 200) {
      refresh(false);
    }
  });
}

onMounted(() => {
  getGlobalConf();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="conf.isErr || plugins.isErr"
      :isPend="plugins.isPend"
      :textState="{
        isPend: $t('api_pending', { name: $t('dashboard_global_config') }),
        isErr: $t('api_error', { name: $t('dashboard_global_config') }),
      }"
    />
    <div
      v-if="!plugins.isErr && !plugins.isPend"
      class="col-span-12 content-wrap"
    >
      <CardBase
        class="z-100 h-fit col-span-12 md:col-span-5 lg:col-span-4 3xl:col-span-3 grid grid-cols-12 relative"
      >
        <CardLabel :label="$t('dashboard_global_config')" />
        <SettingsLayout
          class="flex w-full col-span-12"
          :label="$t('global_conf_select_plugin')"
          name="plugins"
        >
          <SettingsSelect
            @inp="(v) => (plugins.activePlugin = v)"
            :settings="{
              id: 'plugins',
              value: plugins.activePlugin,
              values: plugins.activePlugins,
              placeholder: $t('global_conf_select_plugin_placeholder'),
            }"
          />
        </SettingsLayout>
      </CardBase>
      <CardBase
        :label="$t('dashboard_filter')"
        class="z-10 h-fit col-span-12 md:col-span-7 lg:col-span-5 3xl:col-span-3 grid grid-cols-12 relative"
      >
        <SettingsLayout
          class="flex w-full col-span-12 md:col-span-6"
          :label="$t('global_conf_filter_search')"
          name="keyword"
        >
          <SettingsInput
            @inp="(v) => (filters.keyword = v)"
            :settings="{
              id: 'keyword',
              type: 'text',
              value: '',
              placeholder: $t('global_conf_filter_search_placeholder'),
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12 md:col-span-6"
          :label="$t('global_conf_filter_method')"
          name="method"
        >
          <SettingsSelect
            @inp="(v) => (filters.method = v)"
            :settings="{
              id: 'method',
              value: 'all',
              values: getMethodList(),
            }"
          />
        </SettingsLayout>
      </CardBase>
      <CardBase class="col-span-12 grid grid-cols-12 relative">
        <PluginStructure
          :plugins="plugins.setup"
          :active="plugins.activePlugin"
        />
        <div class="col-span-12 flex w-full justify-center mt-8 mb-2">
          <ButtonBase
            :disabled="
              Object.keys(config.data['global']).length === 0 ? true : false
            "
            @click="sendConf()"
            color="valid"
            size="lg"
          >
            {{ $t("action_save") }}
          </ButtonBase>
        </div>
      </CardBase>
    </div>
  </Dashboard>
</template>
