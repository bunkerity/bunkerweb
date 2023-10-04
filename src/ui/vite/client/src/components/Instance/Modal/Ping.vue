<script setup>
import { defineProps, defineEmits } from "vue";
import ButtonBase from "@components/Button/Base.vue";
import ModalBase from "@components/Modal/Base.vue";
// Open after instance delete action is fired
const props = defineProps({
  // File or folder
  data: {
    type: String,
    required: true,
  },
  isPend: {
    type: Boolean,
    required: true,
  },
  isErr: {
    type: Boolean,
    required: true,
  },
  isOpen: {
    type: Boolean,
    required: true,
  },
  hostname: {
    type: String,
    required: true,
  },
});

const emits = defineEmits(["close"]);
</script>
<template>
  <ModalBase title="ping instance" v-if="props.isOpen">
    <div class="flex justify-center">
      <div class="modal-path">
        <p class="modal-path-text">
          {{
            props.isPend
              ? `Ping ${props.hostname} in progress.`
              : props.isErr
              ? `Error while ${props.hostname}.`
              : !props.data
              ? `Ping success but no additional data from ${props.hostname}.`
              : `Ping result for ${props.hostname} :`
          }}
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
      >
        Close
      </ButtonBase>
    </div>
  </ModalBase>
</template>
