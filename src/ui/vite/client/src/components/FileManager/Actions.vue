<script setup>
import { defineProps, defineEmits } from "vue";

const props = defineProps({
  canCreateFile: {
    type: Boolean,
    required: true,
  },
  canCreateFolder: {
    type: Boolean,
    required: true,
  },
});

const emits = defineEmits(["createFile", "createFolder"]);
</script>

<template>
  <div class="file-manager-actions-container">
    <ul class="file-manager-actions-list">
      <li class="file-manager-actions-item">
        <button
          @click="$emit('createFile')"
          :disabled="props.canCreateFile ? false : true"
          class="file-manager-actions-item-btn"
        >
          <svg
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
          ADD FILE
        </button>
      </li>
      <li class="file-manager-actions-item">
        <button
          @click="$emit('createFolder')"
          :disabled="props.canCreateFolder ? false : true"
          class="file-manager-actions-item-btn"
        >
          <svg
            :class="[
              props.canCreateFolder ? 'active' : 'disabled',
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
              d="M12 10.5v6m3-3H9m4.06-7.19l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"
            />
          </svg>

          ADD FOLDER
        </button>
      </li>
    </ul>
  </div>
</template>
