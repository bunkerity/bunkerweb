<script setup>
import ButtonBase from "@components/Button/Base.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import { reactive, computed, watch } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { useRefreshStore } from "@store/global.js";

// Refresh when related btn is clicked
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  refresh();
});

const feedbackStore = useFeedbackStore();

const pw = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  currPwValue: "",
  newPwValue: "",
  confirmPwValue: "",
  setup: computed(() => {
    if (pw.isErr || pw.isPend || !pw.data) {
      return [];
    }
    return pw.data;
  }),
});

async function updatePw() {
  // Case no data to send
  if (!pw.currPwValue || !pw.newPwValue || !pw.confirmPwValue) return;

  await fetchAPI(
    "/api/account/password",
    "POST",
    {
      password: pw.currPwValue,
      new_password: pw.newPwValue,
      confirm_password: pw.confirmPwValue,
    },
    pw,
    feedbackStore.addFeedback,
  ).then((res) => {
    if (res.status === 200) {
      refresh(false);
    }
  });
}
</script>

<template>
  <div class="col-span-12 grid grid-cols-12">
    <SettingsLayout :label="$t('account_password')" :name="`edit-pw-password`">
      <SettingsInput
        @inp="(v) => (pw.currPwValue = v)"
        :settings="{
          id: `edit-pw-password`,
          type: 'password',
          value: pw.currPwValue,
          placeholder: $t('account_password_placeholder'),
          disabled: true,
        }"
      />
    </SettingsLayout>
    <SettingsLayout
      :label="$t('account_password_new')"
      :name="`edit-pw-new-password`"
    >
      <SettingsInput
        @inp="(v) => (pw.newPwValue = v)"
        :settings="{
          id: `edit-pw-new-password`,
          type: 'password',
          value: pw.newPwValue,
          placeholder: $t('account_password_placeholder'),
          disabled: true,
        }"
      />
    </SettingsLayout>

    <SettingsLayout
      :label="$t('account_password_confirm')"
      :name="`edit-pw-confirm-password`"
    >
      <SettingsInput
        @inp="(v) => (pw.confirmPwValue = v)"
        :settings="{
          id: `edit-pw-confirm-password`,
          type: 'password',
          value: pw.confirmPwValue,
          placeholder: $t('account_password_placeholder'),
          disabled: true,
        }"
      />
    </SettingsLayout>

    <div class="col-span-12 flex justify-center mt-4">
      <ButtonBase
        type="submit"
        @click.prevent="updatePw()"
        color="edit"
        size="normal"
        class="text-sm ml-4"
        :isLoading="pw.isPend"
        :disabled="
          pw.currPwValue && pw.newPwValue && pw.confirmPwValue && !pw.isPend
            ? false
            : true
        "
      >
        {{ $t("action_edit") }}
      </ButtonBase>
    </div>
  </div>
</template>
