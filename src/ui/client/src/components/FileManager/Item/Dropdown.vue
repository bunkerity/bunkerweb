<script setup>
import FileManagerButtonView from "@components/FileManager/Button/View.vue";
import FileManagerButtonEdit from "@components/FileManager/Button/Edit.vue";
import FileManagerButtonDownload from "@components/FileManager/Button/Download.vue";
import FileManagerButtonDelete from "@components/FileManager/Button/Delete.vue";
import { reactive, watch, defineEmits, ref, computed } from "vue";
// Dropdown toggle logic and buttons list with @action emit value on click
// The value of the clicked button will be emit itself to be retrieved by FileManagerBase
const props = defineProps({
  canEdit: {
    type: Boolean,
    required: true,
  },
  canDownload: {
    type: Boolean,
    required: true,
  },
  canDelete: {
    type: Boolean,
    required: true,
  },
});

const dropdown = reactive({
  isOpen: false,
});

const dropdownBtn = ref();

// Close dropdown when clicked outside element
watch(dropdown, () => {
  if (dropdown.isOpen) {
    document.querySelector("body").addEventListener("click", closeOutside);
  } else {
    document.querySelector("body").removeEventListener("click", closeOutside);
  }
});

// Close dropdown when clicked outside logic
function closeOutside(e) {
  try {
    if (e.target !== dropdownBtn.value) {
      dropdown.isOpen = false;
    }
  } catch (err) {
    dropdown.isOpen = false;
  }
}

const emits = defineEmits(["action"]);
</script>

<template>
  <button
    ref="dropdownBtn"
    @click="dropdown.isOpen = dropdown.isOpen ? false : true"
    data-action-dropdown
    :aria-expanded="dropdown.isOpen ? 'true' : 'false'"
    class="file-manager-item-dropdown-btn"
  >
    <svg
      class="pointer-events-none h-8 w-8 fill-white"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke-width="1.5"
      stroke="currentColor"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M12 6.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 12.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 18.75a.75.75 0 110-1.5.75.75 0 010 1.5z"
      />
    </svg>
  </button>
  <!-- dropdown -->
  <div v-if="dropdown.isOpen" role="tablist" class="file-manager-item-dropdown">
    <FileManagerButtonView
      class="first"
      :class="[
        props.canDelete || props.canDownload || props.canEdit ? '' : 'last',
      ]"
      @click="$emit('action', 'view')"
    />
    <FileManagerButtonEdit
      @click="$emit('action', 'edit')"
      v-if="props.canEdit"
      :class="[props.canDelete || props.canDownload ? '' : 'last']"
    />
    <FileManagerButtonDownload
      @click="$emit('action', 'download')"
      v-if="props.canDownload"
      :class="[props.canDelete ? '' : 'last']"
    />
    <FileManagerButtonDelete
      @click="$emit('action', 'delete')"
      v-if="props.canDelete"
      class="last"
    />
  </div>
  <!-- end dropdown -->
</template>
