<script setup>
import { reactive, watch } from "vue";
import ButtonBase from "@components/Button/Base.vue";
import ModalBase from "@components/Modal/Base.vue";
import { contentIndex } from "@utils/tabindex.js";
import {
  useBackdropStore,
  useRefreshStore,
  useFeedbackStore,
} from "@store/global.js";
import { useModalStore } from "@store/instances.js";
import { fetchAPI } from "@utils/api.js";

const feedbackStore = useFeedbackStore();
const refreshStore = useRefreshStore();
const modalStore = useModalStore();
const backdropStore = useBackdropStore();

// close modal on backdrop click
watch(backdropStore, () => {
  modalStore.isOpen = false;
});

const instDel = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

async function deleteInstance() {
  //Try action and refetch instances only if succeed
  await fetchAPI(
    `/api/instances/${modalStore.data.hostname}?method=ui`,
    "DELETE",
    null,
    instDel,
    feedbackStore.addFeedback,
  ).then((res) => {
    if (res.type === "success") {
      refreshStore.refresh();
      return;
    }
  });
}
</script>
<template>
  <ModalBase
    :title="$t('instances_modal_delete_title')"
    id="instance-modal"
    :aria-hidden="modalStore.isOpen ? 'false' : 'true'"
    v-if="modalStore.isOpen"
  >
    <div class="w-full">
      <div class="flex justify-center">
        <div class="modal-path">
          <p class="modal-path-text">
            {{
              $t("instances_modal_delete_msg", {
                hostname: modalStore.data.hostname,
              })
            }}
          </p>
        </div>
      </div>
      <div class="mt-2 w-full justify-end flex">
        <ButtonBase
          :tabindex="modalStore.isOpen ? contentIndex : -1"
          color="close"
          size="lg"
          @click="modalStore.isOpen = false"
          type="button"
          class="text-xs"
          aria-controls="instance-modal"
          :aria-expanded="modalStore.isOpen ? 'true' : 'false'"
        >
          {{ $t("action_close") }}
        </ButtonBase>
        <ButtonBase
          :isLoading="updateConf.isPend"
          :disabled="updateConf.isPend"
          type="submit"
          :tabindex="modalStore.isOpen ? contentIndex : -1"
          color="delete"
          size="lg"
          @click.prevent="deleteInstance()"
          class="text-xs ml-2"
        >
          {{ $t("action_delete") }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
