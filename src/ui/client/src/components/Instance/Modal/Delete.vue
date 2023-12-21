<script setup>
import { defineProps, defineEmits } from "vue";
import ButtonBase from "@components/Button/Base.vue";
import ModalBase from "@components/Modal/Base.vue";
// Open after instance delete action is fired
const props = defineProps({
  // File or folder
  hostname: {
    type: String,
    required: true,
  },
  isOpen: {
    type: Boolean,
    required: true,
  },
});

const emits = defineEmits(["close", "delete"]);
</script>
<template>
  <ModalBase
    @backdrop="$emit('close')"
    :title="$t('instances_modal_delete_title')"
    id="instance-modal"
    :aria-hidden="props.isOpen ? 'false' : 'true'"
    v-if="props.isOpen"
  >
    <div class="w-full">
      <div class="flex justify-center">
        <div class="modal-path">
          <p class="modal-path-text">
            {{ $t("instances_modal_delete_msg", { hostname: props.hostname }) }}
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
          aria-controls="instance-modal"
          :aria-expanded="props.isOpen ? 'true' : 'false'"
        >
          {{ $t("action_close") }}
        </ButtonBase>
        <ButtonBase
          color="delete"
          size="lg"
          @click="
            () => {
              $emit('close');
              $emit('delete', { hostname: props.hostname });
            }
          "
          class="text-xs ml-2"
        >
          {{ $t("action_delete") }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
