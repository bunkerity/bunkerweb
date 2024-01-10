<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import CardBase from "@components/Card/Base.vue";
import CardLabel from "@components/Card/Label.vue";
import AccountTabs from "@components/Account/Tabs.vue";
import AccountUsername from "@components/Account/Username.vue";
import AccountPassword from "@components/Account/Password.vue";
import AccountTotp from "@components/Account/Totp.vue";
import { reactive, computed, onMounted, watch } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";

// Refresh when related btn is clicked
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  refresh();
});

const logsStore = useLogsStore();
logsStore.setTags(["account"]);

const feedbackStore = useFeedbackStore();

// Plugins data to render components
const account = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  currTab: "username",
  setup: computed(() => {
    if (account.isErr || account.isPend || !account.data) {
      return [];
    }

    return account.data;
  }),
});

async function getAccount() {
  await fetchAPI(
    "/api/account",
    "GET",
    null,
    account,
    feedbackStore.addFeedback
  );
}

onMounted(() => {
  getAccount();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="account.isErr"
      :isPend="account.isPend"
      :textState="{
        isPend: $t('api_pending', { name: $t('dashboard_account') }),
        isErr: $t('api_error', { name: $t('dashboard_account') }),
      }"
    />
    <div
      v-if="!account.isErr && !account.isPend"
      class="col-span-12 content-wrap"
    >
      <CardBase
        class="z-100 h-fit col-span-12 md:col-span-5 lg:col-span-4 3xl:col-span-3 grid grid-cols-12 relative"
      >
        <CardLabel :label="$t('account_settings')" />
        <AccountTabs @tab="(v) => (account.currTab = v)" />
        <AccountUsername
          v-show="account.currTab === 'username'"
          :currUsername="account.setup.username"
        />
        <AccountPassword v-show="account.currTab === 'password'" />
        <AccountTotp v-show="account.currTab === 'totp'" />
      </CardBase>
    </div>
  </Dashboard>
</template>
