<script setup>
import { reactive, watch } from "vue";
import ModalBase from "@components/Modal/Base.vue";
import ButtonBase from "@components/Button/Base.vue";
import { fetchAPI } from "@utils/api.js";
import { contentIndex } from "@utils/tabindex.js";
import {
  useFeedbackStore,
  useBackdropStore,
  useRefreshStore,
} from "@store/global.js";
import { useDelModalStore } from "@store/services.js";

const backdropStore = useBackdropStore();
const delModalStore = useDelModalStore();
const feedbackStore = useFeedbackStore();
const refreshStore = useRefreshStore();

// Close modal on backdrop click
watch(backdropStore, () => {
  delModalStore.isOpen = false;
});

const deleteServ = reactive({
  serviceName: "",
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
});

watch(delModalStore, () => {
  deleteServ.serviceName = delModalStore.data.serviceName;
});

async function delServ() {
  await fetchAPI(
    `/api/config/service/${deleteServ.serviceName}?method=ui`,
    "DELETE",
    null,
    deleteServ,
    feedbackStore.addFeedback
  )
    .then((res) => {
      // Case saved, close modal, go to root path and refresh
      if (res.type === "success") {
        delModalStore.$reset();
        delModalStore.isOpen = false;
        refreshStore.refresh();
        return;
      }
    })
    .catch((err) => {});
}
</script>
<template>
  <ModalBase
    id="service-delete-modal"
    :aria-hidden="delModalStore.isOpen ? 'false' : 'true'"
    :title="$t('services_delete_title')"
    v-show="delModalStore.isOpen"
  >
    <div class="w-full">
      <div class="flex justify-center">
        <div class="modal-path">
          <p class="modal-path-text">
            {{ $t("services_delete_msg", { name: delServ.serviceName }) }}
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
          class="text-xs"
          aria-controls="service-delete-modal"
          :aria-expanded="delModalStore.isOpen ? 'true' : 'false'"
        >
          {{ $t("action_close") }}
        </ButtonBase>
        <ButtonBase
          :tabindex="delModalStore.isOpen ? contentIndex : -1"
          type="submit"
          color="delete"
          size="lg"
          @click.prevent="delServ()"
          class="text-xs ml-2"
        >
          {{ $t("action_delete") }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
