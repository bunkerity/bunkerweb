<script setup>
import { onMounted, onUnmounted } from "vue";

const props = defineProps({
  title: {
    type: String,
    required: false,
    default: "",
  },
});

const emits = defineEmits(["backdrop"]);

function closeBackdrop(e) {
  try {
    if (
      e.target.className.includes("modal-container") ||
      e.target.className.includes("modal-wrap")
    ) {
      emits("backdrop");
    }
  } catch (e) {}
}

onMounted(() => {
  window.addEventListener("click", closeBackdrop);
});

onUnmounted(() => {
  window.removeEventListener("click", closeBackdrop);
});
</script>

<template>
  <div class="modal-container">
    <div class="modal-wrap">
      <div class="modal-card">
        <div v-if="props.title" class="w-full flex justify-between">
          <p class="modal-card-title">{{ props.title }}</p>
        </div>
        <slot></slot>
      </div>
    </div>
  </div>
</template>
