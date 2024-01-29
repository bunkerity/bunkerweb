<script setup>
import { reactive, watch } from "vue";
import ButtonBase from "@components/Button/Base.vue";
import ModalBase from "@components/Modal/Base.vue";
import { fetchAPI } from "@utils/api.js";
import { contentIndex } from "@utils/tabindex.js";
import {
  useFeedbackStore,
  useBackdropStore,
  useRefreshStore,
} from "@store/global.js";
import { useDelModalStore } from "@store/plugins.js";

const backdropStore = useBackdropStore();
const feedbackStore = useFeedbackStore();
const delModalStore = useDelModalStore();
const refreshStore = useRefreshStore();

// close modal on backdrop click
watch(backdropStore, () => {
  if (delPlugin.isPend) return;
  delModalStore.isOpen = false;
});

watch(delModalStore, (newVal, oldVal) => {
  delPlugin.id = newVal.data.id;
  delPlugin.name = newVal.data.name;
  delPlugin.description = newVal.data.description;

  if (newVal.isOpen) {
    // Force tabindex
    setTimeout(() => {
      document.querySelector("#plugin-delete-modal button").focus();
    }, 100);
    return;
  }
});

const delPlugin = reactive({
  isErr: false,
  isPend: false,
  data: [],
  id: "",
  name: "",
  description: "",
});

async function pluginDelete() {
  await fetchAPI(
    `/api/plugins/${delPlugin.id}?method=ui`,
    "DELETE",
    null,
    delPlugin,
    feedbackStore.addFeedback,
  ).then((res) => {
    if (res.type === "success") {
      delModalStore.isOpen = false;
      refreshStore.refresh();
    }
  });
}
</script>
<template>
  <ModalBase
    id="plugin-delete-modal"
    :aria-hidden="delModalStore.isOpen ? 'false' : 'true'"
    :title="$t('plugins_delete_modal_title', { name: delPlugin.name })"
    v-show="delModalStore.isOpen"
  >
    <div class="col-span-12 overflow-x-auto overflow-y-hidden">
      <p class="text-base">
        {{ $t("plugins_delete_modal_text", { name: delPlugin.name }) }}
      </p>
      <p>{{ delPlugin.description }}</p>
    </div>

    <div class="w-full mt-2">
      <div class="mt-2 w-full justify-end flex">
        <ButtonBase
          :tabindex="delModalStore.isOpen ? contentIndex : '-1'"
          color="close"
          size="lg"
          @click="delModalStore.isOpen = false"
          type="button"
          class="text-sm"
          :disabled="delPlugin.isPend"
          aria-controls="plugin-delete-modal"
          :aria-expanded="delModalStore.isOpen ? 'true' : 'false'"
        >
          {{ $t("action_close") }}
        </ButtonBase>
        <ButtonBase
          :isLoading="delPlugin.isPend"
          :disabled="delPlugin.isPend"
          :tabindex="delModalStore.isOpen ? contentIndex : '-1'"
          type="submit"
          color="delete"
          size="lg"
          @click.prevent="pluginDelete()"
          class="text-sm"
        >
          {{ $t("action_delete") }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
