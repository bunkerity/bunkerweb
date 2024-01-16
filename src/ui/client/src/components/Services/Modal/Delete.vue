<script setup>
import { defineProps, defineEmits, reactive } from "vue";
import ModalBase from "@components/Modal/Base.vue";
import ButtonBase from "@components/Button/Base.vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";

const feedbackStore = useFeedbackStore();

// Open after a file manager item (folder / file) action is clicked
// With the current folder / file data
// Update name or content file if wanted
const props = defineProps({
  // File value is shown with an editor
  serviceName: {
    type: String,
    required: true,
    default: "",
  },
  isOpen: {
    type: Boolean,
    required: true,
    default: false,
  },
});

const deleteServ = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
});

async function delServ() {
  await fetchAPI(
    `/api/config/service/${props.serviceName}?method=ui`,
    "DELETE",
    null,
    deleteServ,
    feedbackStore.addFeedback,
  )
    .then((res) => {
      // Case saved
      if (res.type === "success") {
        emits("delete");
        emits("close");
        return;
      }
    })
    .catch((err) => {});
}

const emits = defineEmits(["close", "delete"]);
</script>
<template>
  <ModalBase
    id="service-delete-modal"
    :aria-hidden="props.isOpen ? 'false' : 'true'"
    @backdrop="$emit('close')"
    :title="$t('services_delete_title')"
    v-if="props.isOpen"
  >
    <div class="w-full">
      <div class="flex justify-center">
        <div class="modal-path">
          <p class="modal-path-text">
            {{ $t("services_delete_msg", { name: props.serviceName }) }}
          </p>
        </div>
      </div>
      <div class="mt-2 w-full justify-end flex">
        <ButtonBase
          color="close"
          size="lg"
          @click="$emit('close')"
          type="button"
          class="text-xs"
          aria-controls="service-delete-modal"
          :aria-expanded="props.isOpen ? 'true' : 'false'"
        >
          {{ $t("action_close") }}
        </ButtonBase>
        <ButtonBase
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
