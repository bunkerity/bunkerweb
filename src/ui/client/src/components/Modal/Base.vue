<script setup>
import { useBackdropStore } from "@store/global.js";
import { ref, onMounted } from "vue";

const backdropStore = useBackdropStore();

const container = ref();
const wrap = ref();

onMounted(() => {
  window.addEventListener("click", (e) => {
    if (e.target === container.value || e.target === wrap.value)
      return backdropStore.clickCount++;
  });
});

const props = defineProps({
  title: {
    type: String,
    required: false,
    default: "",
  },
  //regular, large
  cardSize: {
    type: String,
    required: false,
    default: "regular",
  },
});
</script>

<template>
  <div ref="container" class="modal-container">
    <div ref="wrap" class="modal-wrap">
      <div :class="[props.cardSize]" class="modal-card">
        <div v-if="props.title" class="w-full flex justify-between">
          <p class="modal-card-title">{{ props.title }}</p>
        </div>
        <slot></slot>
      </div>
    </div>
  </div>
</template>
