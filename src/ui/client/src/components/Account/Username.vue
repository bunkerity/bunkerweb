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

const props = defineProps({
  currUsername: {
    type: String,
    required: false,
    default: "",
  },
});

const username = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  userValue: props.currUsername,
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
  if (!username.userValue || !username.pwValue) return;

  await fetchAPI(
    "/api/account/username",
    "POST",
    { username: username.value, password: username.pwValue },
    username,
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
          placeholder: $t('account_username_placeholder'),
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
          placeholder: $t('account_password_placeholder'),
          disabled: true,
        }"
      />
    </SettingsLayout>

    <div class="col-span-12 flex justify-center mt-4">
      <ButtonBase
        @click.prevent="updateUsername()"
        color="edit"
        size="normal"
        class="text-sm ml-4"
        type="submit"
        :disabled="username.userValue && username.pwValue ? false : true"
      >
        {{ $t("action_edit") }}
      </ButtonBase>
    </div>
  </div>
</template>
