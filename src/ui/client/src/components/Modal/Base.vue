<script setup>
import { useBackdropStore } from "@store/global.js";

const backdropStore = useBackdropStore();

const props = defineProps({
  title: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <div @click="backdropStore.clickCount++" class="modal-container">
    <div @click="backdropStore.clickCount++" class="modal-wrap">
      <div class="modal-card">
        <div v-if="props.title" class="w-full flex justify-between">
          <p class="modal-card-title">{{ props.title }}</p>
        </div>
        <slot></slot>
      </div>
    </div>
  </div>
</template>
