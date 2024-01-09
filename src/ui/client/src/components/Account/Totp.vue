<script setup>
import ButtonBase from "@components/Button/Base.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import { reactive, computed, watch } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { useRefreshStore } from "@store/global.js";
import { onMounted } from "vue";

// Refresh when related btn is clicked
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  refresh();
});

const feedbackStore = useFeedbackStore();

const props = defineProps({
  isTotp: {
    type: Boolean,
    required: true,
    default: false,
  },
});

const secretKey = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  setup: computed(() => {
    if (totp.isErr || totp.isPend || !totp.data) {
      return [];
    }
    return totp.data;
  }),
});

async function generateSecretKey() {
  await fetchAPI(
    "/api/account/secret",
    "GET",
    null,
    totp,
    feedbackStore.addFeedback
  ).then((res) => {
    if (res.status === 200) {
      refresh(false);
    }
  });
}

const totp = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  codeValue: "",
  pwValue: "",
  setup: computed(() => {
    if (totp.isErr || totp.isPend || !totp.data) {
      return [];
    }
    return totp.data;
  }),
});

async function updateTotp() {
  // Case no data to send
  if (!totp.codeValue || !totp.pwValue) return;

  await fetchAPI(
    "/api/database/account/totp",
    "POST",
    { code: totp.code, password: totp.password },
    totp,
    feedbackStore.addFeedback
  ).then((res) => {
    if (res.status === 200) {
      refresh(false);
    }
  });
}

onMounted(() => {
  generateSecretKey();
});
</script>

<template>
  <div v-if="props.isTotp" class="col-span-12 grid grid-cols-12">
    <SettingsLayout
      :label="$t('account_username')"
      :name="`edit-username-username`"
    >
      <SettingsInput
        @inp="(v) => (username.userValue = v)"
        :settings="{
          id: `edit-username-username`,
          type: 'text',
          value: username.userValue,
          placeholder: 'username',
          disabled: true,
        }"
      />
    </SettingsLayout>
    <SettingsLayout
      :label="$t('account_password')"
      :name="`edit-username-password`"
    >
      <SettingsInput
        @inp="(v) => (username.pwValue = v)"
        :settings="{
          id: `edit-username-password`,
          type: 'password',
          value: username.pwValue,
          placeholder: 'P@ssw0rd',
          disabled: true,
        }"
      />
    </SettingsLayout>

    <div class="col-span-12 flex justify-center mt-4">
      <ButtonBase
        @click="updateUsername()"
        :aria-description="$t('account_edit_username_desc')"
        color="edit"
        size="normal"
        class="text-sm ml-4"
        :disabled="username.userValue && username.pwValue ? false : true"
      >
        {{ $t("action_edit") }}
      </ButtonBase>
    </div>
  </div>
</template>
