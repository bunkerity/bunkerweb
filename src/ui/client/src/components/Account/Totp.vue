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
    `/api/account/totp?method=ui&action=${props.isTotp ? "disable" : "enable"}`,
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
  <div class="col-span-12 grid grid-cols-12">
    <SettingsLayout
      v-if="!props.isTotp"
      :label="$t('account_totp_qr_code')"
      :name="`edit-totp-qr-code`"
    >
    </SettingsLayout>
    <SettingsLayout
      v-if="!props.isTotp"
      :label="$t('account_totp_secret')"
      :name="`edit-totp-secret`"
    >
      <SettingsInput
        :settings="{
          id: `edit-totp-secret`,
          type: 'password',
          value: secretkey.setup.secret,
          placeholder: $t('account_totp_secret_placeholder'),
          disabled: true,
        }"
      />
    </SettingsLayout>
    <SettingsLayout :label="$t('account_totp_code')" :name="`edit-totp-code`">
      <SettingsInput
        @inp="(v) => (totp.code = v)"
        :settings="{
          id: `edit-totp-code`,
          type: 'text',
          value: totp.codeValue,
          placeholder: $t('account_totp_code_placeholder'),
        }"
      />
    </SettingsLayout>

    <SettingsLayout
      :label="$t('account_password')"
      :name="`edit-totp-password`"
    >
      <SettingsInput
        @inp="(v) => (totp.pwValue = v)"
        :settings="{
          id: `edit-totp-password`,
          type: 'password',
          value: totp.pwValue,
          placeholder: $t('account_password_placeholder'),
        }"
      />
    </SettingsLayout>

    <div class="col-span-12 flex justify-center mt-4">
      <ButtonBase
        @click="updateTotp()"
        :aria-description="$t('account_edit_totp_desc')"
        color="edit"
        size="normal"
        class="text-sm ml-4"
        :disabled="totp.codeValue && totp.pwValue ? false : true"
      >
        {{ props.isTotp ? $t("action_disable") : $t("action_enable") }}
      </ButtonBase>
    </div>
  </div>
</template>
