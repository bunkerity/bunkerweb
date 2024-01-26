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
import { useEditModalStore } from "@store/instances.js";
import { fetchAPI } from "@utils/api.js";

const feedbackStore = useFeedbackStore();
const refreshStore = useRefreshStore();
const editModalStore = useEditModalStore();
const backdropStore = useBackdropStore();

// close modal on backdrop click
watch(backdropStore, () => {
  if (instEdit.isPend) return;
  editModalStore.isOpen = false;
});

watch(editModalStore, () => {
  if (editModalStore.isOpen) {
    // Force tabindex
    setTimeout(() => {
      document.querySelector("#edit-instance-modal input").focus();
    }, 100);
    return;
  }

  instEdit.hostname = editModalStore.isOpen
    ? editModalStore.data.hostname || ""
    : "";
  instEdit.serverName = editModalStore.isOpen
    ? editModalStore.data.serverName || ""
    : "";
  instEdit.oldHostname = editModalStore.isOpen
    ? editModalStore.data.hostname || ""
    : "";
  instEdit.port = editModalStore.isOpen ? editModalStore.data.port || "" : "";
});

const instEdit = reactive({
  isPend: false,
  isErr: false,
  data: [],
  hostname: "",
  oldHostname: "",
  serverName: "",
  port: "",
});

async function editInstance() {
  const data = {
    hostname: instEdit.hostname,
    old_hostname: instEdit.oldHostname,
    server_name: instEdit.serverName,
    port: instEdit.port,
  };

  //Try action and refetch instances only if succeed
  await fetchAPI(
    `/api/instances?method=ui&reload=true`,
    "PUT",
    data,
    instEdit,
    feedbackStore.addFeedback
  ).then((res) => {
    if (res.type === "success") {
      editModalStore.isOpen = false;
      refreshStore.refresh();
      return;
    }
  });
}
</script>
<template>
  <ModalBase
    :title="$t('instances_modal_edit_title', { name: instEdit.oldHostname })"
    id="edit-instance-modal"
    :aria-hidden="editModalStore.isOpen ? 'false' : 'true'"
    v-show="editModalStore.isOpen"
  >
    <div class="w-full flex flex-col justify-center items-center">
      <div class="grid grid-cols-12 w-full max-w-[300px]">
        <SettingsLayout
          class="flex w-full col-span-12"
          :label="$t('instances_hostname')"
          name="edit-hostname"
          :key="editModalStore.isOpen"
        >
          <SettingsInput
            @inp="(v) => (instEdit.hostname = v)"
            :settings="{
              id: 'edit-hostname',
              type: 'text',
              value: instEdit.hostname || instEdit.oldHostname,
              placeholder: $t('instances_hostname_placeholder'),
              required: true,
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12"
          :label="$t('instances_server_name')"
          name="edit-server-name"
          :key="editModalStore.isOpen"
        >
          <SettingsInput
            @inp="(v) => (instEdit.serverName = v)"
            :settings="{
              id: 'edit-server-name',
              type: 'text',
              value: instEdit.serverName,
              placeholder: $t('instances_server_name_placeholder'),
              required: true,
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12"
          :label="$t('instances_port')"
          name="edit-port"
          :key="editModalStore.isOpen"
        >
          <SettingsInput
            @inp="(v) => (instEdit.port = v)"
            :settings="{
              id: 'edit-port',
              type: 'text',
              value: instEdit.port,
              placeholder: $t('instances_port_placeholder'),
              required: true,
            }"
          />
        </SettingsLayout>
      </div>

      <div class="mt-2 w-full justify-end flex">
        <ButtonBase
          :tabindex="editModalStore.isOpen ? contentIndex : -1"
          color="close"
          size="lg"
          @click="editModalStore.isOpen = false"
          type="button"
          class="text-sm"
          :disabled="instEdit.isPend"
          aria-controls="edit-instance-modal"
          :aria-expanded="editModalStore.isOpen ? 'true' : 'false'"
        >
          {{ $t("action_close") }}
        </ButtonBase>
        <ButtonBase
          :isLoading="instEdit.isPend"
          :disabled="
            instEdit.isPend ||
            !instEdit.port ||
            !instEdit.hostname ||
            !instEdit.serverName
          "
          type="submit"
          :tabindex="editModalStore.isOpen ? contentIndex : -1"
          color="edit"
          size="lg"
          @click.prevent="editInstance()"
          class="text-sm ml-2"
        >
          {{ $t("action_edit") }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
