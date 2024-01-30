<script setup>
import { reactive, watch } from "vue";
import ButtonBase from "@components/Button/Base.vue";
import ModalBase from "@components/Modal/Base.vue";
import { contentIndex } from "@utils/tabindex.js";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import {
  useBackdropStore,
  useRefreshStore,
  useFeedbackStore,
} from "@store/global.js";
import { useAddModalStore } from "@store/instances.js";
import { fetchAPI } from "@utils/api.js";

const feedbackStore = useFeedbackStore();
const refreshStore = useRefreshStore();
const addModalStore = useAddModalStore();
const backdropStore = useBackdropStore();

// close modal on backdrop click
watch(backdropStore, () => {
  if (instAdd.isPend) return;
  addModalStore.isOpen = false;
});

watch(addModalStore, () => {
  if (addModalStore.isOpen) {
    // Force tabindex
    setTimeout(() => {
      document.querySelector("#add-instance-modal input").focus();
    }, 100);
    return;
  }

  if (!addModalStore.isOpen) {
    // Reset values
    instAdd.hostname = "";
    instAdd.serverName = "";
    instAdd.port = "";
    instAdd.resetCount++;
  }
});

const instAdd = reactive({
  isPend: false,
  isErr: false,
  data: [],
  resetCount: 0,
  hostname: "",
  serverName: "",
  port: "",
});

async function addInstance() {
  const data = {
    hostname: instAdd.hostname,
    server_name: instAdd.serverName,
    port: instAdd.port,
  };

  //Try action and refetch instances only if succeed
  await fetchAPI(
    `/api/instances?method=ui&reload=true`,
    "PUT",
    data,
    instAdd,
    feedbackStore.addFeedback,
  ).then((res) => {
    if (res.type === "success") {
      addModalStore.isOpen = false;
      refreshStore.refresh();
      return;
    }
  });
}
</script>
<template>
  <ModalBase
    :title="$t('instances_modal_add_title')"
    id="add-instance-modal"
    :aria-hidden="addModalStore.isOpen ? 'false' : 'true'"
    v-show="addModalStore.isOpen"
  >
    <div class="w-full flex flex-col justify-center items-center">
      <div class="grid grid-cols-12 w-full max-w-[300px]">
        <SettingsLayout
          class="flex w-full col-span-12"
          :label="$t('instances_hostname')"
          name="add-hostname"
          :key="instAdd.resetCount"
        >
          <SettingsInput
            @inp="(v) => (instAdd.hostname = v)"
            :settings="{
              id: 'add-hostname',
              type: 'text',
              value: instAdd.hostname,
              placeholder: $t('instances_hostname_placeholder'),
              required: true,
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12"
          :label="$t('instances_server_name')"
          name="add-server-name"
          :key="instAdd.resetCount"
        >
          <SettingsInput
            @inp="(v) => (instAdd.serverName = v)"
            :settings="{
              id: 'add-server-name',
              type: 'text',
              value: instAdd.serverName,
              placeholder: $t('instances_server_name_placeholder'),
              required: true,
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12"
          :label="$t('instances_port')"
          name="add-port"
          :key="instAdd.resetCount"
        >
          <SettingsInput
            @inp="(v) => (instAdd.port = v)"
            :settings="{
              id: 'add-port',
              type: 'text',
              value: instAdd.port,
              placeholder: $t('instances_port_placeholder'),
              required: true,
            }"
          />
        </SettingsLayout>
      </div>

      <div class="mt-4 w-full justify-end flex">
        <ButtonBase
          :tabindex="addModalStore.isOpen ? contentIndex : -1"
          color="close"
          size="lg"
          @click="addModalStore.isOpen = false"
          type="button"
          class="text-sm"
          :disabled="instAdd.isPend"
          aria-controls="add-instance-modal"
          :aria-expanded="addModalStore.isOpen ? 'true' : 'false'"
        >
          {{ $t("action_close") }}
        </ButtonBase>
        <ButtonBase
          :isLoading="instAdd.isPend"
          :disabled="
            instAdd.isPend ||
            !instAdd.port ||
            !instAdd.hostname ||
            !instAdd.serverName
          "
          type="submit"
          :tabindex="addModalStore.isOpen ? contentIndex : -1"
          color="valid"
          size="lg"
          @click.prevent="addInstance()"
          class="text-sm ml-2"
        >
          {{ $t("action_add") }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
