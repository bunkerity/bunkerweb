<script setup>
import { defineProps, defineEmits } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import { useModalStore } from "@store/configs.js";

const modalStore = useModalStore();

const props = defineProps({
  canCreateFile: {
    type: Boolean,
    required: true,
  },
});

const emits = defineEmits(["createFile"]);
</script>

<template>
  <div class="file-manager-actions-container">
    <ul class="file-manager-actions-list">
      <li class="file-manager-actions-item">
        <button
          :tabindex="contentIndex"
          @click="$emit('createFile')"
          :disabled="props.canCreateFile ? false : true"
          :aria-disabled="props.canCreateFile ? false : true"
          aria-controls="file-manager-modal"
          :aria-expanded="modalStore.isOpen ? 'true' : 'false'"
          class="file-manager-actions-item-btn"
        >
          <svg
            role="img"
            aria-hidden="true"
            :class="[
              props.canCreateFile ? 'active' : 'disabled',
              ,
              'file-manager-actions-svg',
            ]"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m3.75 9v6m3-3H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
            />
          </svg>
          {{ $t("custom_conf_add_file") }}
        </button>
      </li>
    </ul>
  </div>
</template>
