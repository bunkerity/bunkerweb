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
import { useDelModalStore } from "@store/instances.js";
import { fetchAPI } from "@utils/api.js";

const feedbackStore = useFeedbackStore();
const refreshStore = useRefreshStore();
const delModalStore = useDelModalStore();
const backdropStore = useBackdropStore();

// close modal on backdrop click
watch(backdropStore, () => {
  if (instDel.isPend) return;
  delModalStore.isOpen = false;
});

watch(delModalStore, () => {
  // Force tabindex
  if (delModalStore.isOpen) {
    setTimeout(() => {
      document.querySelector("#delete-instance-modal button").focus();
    }, 100);
  }
});

const instDel = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

async function deleteInstance() {
  //Try action and refetch instances only if succeed
  await fetchAPI(
    `/api/instances/${delModalStore.data.hostname}?method=ui`,
    "DELETE",
    null,
    instDel,
    feedbackStore.addFeedback,
  ).then((res) => {
    if (res.type === "success") {
      delModalStore.isOpen = false;
      refreshStore.refresh();
      return;
    }
  });
}
</script>
<template>
  <ModalBase
    :title="$t('instances_modal_delete_title')"
    id="delete-instance-modal"
    :aria-hidden="delModalStore.isOpen ? 'false' : 'true'"
    v-show="delModalStore.isOpen"
  >
    <div class="w-full">
      <div class="flex justify-center">
        <div class="modal-path">
          <p class="modal-path-text">
            {{
              $t("instances_modal_delete_msg", {
                hostname: delModalStore.data.hostname,
              })
            }}
          </p>
        </div>
      </div>
      <div class="mt-2 w-full justify-end flex">
        <ButtonBase
          :tabindex="delModalStore.isOpen ? contentIndex : -1"
          color="close"
          size="lg"
          @click="delModalStore.isOpen = false"
          type="button"
          class="text-sm"
          :disabled="instDel.isPend"
          aria-controls="delete-instance-modal"
          :aria-expanded="delModalStore.isOpen ? 'true' : 'false'"
        >
          {{ $t("action_close") }}
        </ButtonBase>
        <ButtonBase
          :isLoading="instDel.isPend"
          :disabled="instDel.isPend"
          type="submit"
          :tabindex="delModalStore.isOpen ? contentIndex : -1"
          color="delete"
          size="lg"
          @click.prevent="deleteInstance()"
          class="text-sm ml-2"
        >
          {{ $t("action_delete") }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
