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
  <ModalBase title="delete instance" v-if="props.isOpen">
    <div class="w-full">
      <div class="flex justify-center">
        <div class="modal-path">
          <p class="modal-path-text">
            {{
              `Are you sure to delete instance with hostname ${props.hostname} ?`
            }}
          </p>
        </div>
      </div>
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />

      <div class="mt-2 w-full justify-end flex">
        <ButtonBase
          color="close"
          size="lg"
          @click="$emit('close')"
          type="button"
          class="text-xs"
        >
          Close
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
          DELETE
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
