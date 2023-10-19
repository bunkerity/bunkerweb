<script setup>
import { defineProps, defineEmits } from "vue";
import ButtonBase from "@components/Button/Base.vue";
import ModalBase from "@components/Modal/Base.vue";
// Open after instance delete action is fired
const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true,
  },
});

const emits = defineEmits(["close", "sendAdd"]);
</script>
<template>
  <ModalBase title="invalid ban items" v-if="props.isOpen">
    <div class="w-full">
      <div class="flex justify-center">
        <div class="modal-path">
          <p class="modal-path-text">
            {{
              `Ban item(s) with invalid format found. They will be ignore on send.`
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
        <ButtonBase
          color="valid"
          size="lg"
          @click="
            () => {
              $emit('close');
              $emit('sendAdd');
            }
          "
          class="text-xs ml-2"
        >
          Save
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
