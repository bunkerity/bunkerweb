<script setup>
import FileManagerButtonView from "@components/FileManager/Button/View.vue";
import FileManagerButtonEdit from "@components/FileManager/Button/Edit.vue";
import FileManagerButtonDownload from "@components/FileManager/Button/Download.vue";
import FileManagerButtonDelete from "@components/FileManager/Button/Delete.vue";
import { reactive, watch, defineEmits, ref } from "vue";
import { v4 as uuidv4 } from "uuid";
import { contentIndex } from "@utils/tabindex.js";
import { useModalStore } from "@store/configs.js";

const modalStore = useModalStore();

// Dropdown toggle logic and buttons list with @action emit value on click
// The value of the clicked button will be emit itself to be retrieved by FileManagerBase
const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
  rights: {
    type: Object,
    required: true,
  },
});

const dropdown = reactive({
  isOpen: false,
  id: uuidv4(),
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

function runAction(action) {
  // keep current path when action open a modal
  // set current action
  const data = props.data;
  data.action = action;
  data.path = modalStore.data.path;
  modalStore.data = data;
  modalStore.isOpen = true;
}
</script>

<template>
  <button
    :tabindex="modalStore.isOpen ? '-1' : contentIndex"
    ref="dropdownBtn"
    @click="dropdown.isOpen = dropdown.isOpen ? false : true"
    data-action-dropdown
    :aria-expanded="dropdown.isOpen ? 'true' : 'false'"
    :aria-controls="`file-manager-${dropdown.id}-dropdown`"
    class="file-manager-item-dropdown-btn"
    :aria-describedby="`${props.id}-dropdown-text`"
  >
    <span :id="`${props.id}-dropdown-text`" class="sr-only">
      {{ $t("custom_conf_dropdown_action") }}
    </span>
    <svg
      aria-hidden="true"
      role="img"
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
  <div
    :id="`file-manager-${dropdown.id}-dropdown`"
    :aria-hidden="dropdown.isOpen ? 'false' : 'true'"
    v-show="dropdown.isOpen"
    role="tablist"
    class="file-manager-item-dropdown"
  >
    <FileManagerButtonView
      role="tab"
      :tabindex="
        dropdown.isOpen ? (modalStore.isOpen ? '-1' : contentIndex) : '-1'
      "
      class="first"
      :class="[
        props.rights.canDelete ||
        props.rights.canDownload ||
        props.rights.canEdit
          ? ''
          : 'last',
      ]"
      @click="runAction('view')"
    />
    <FileManagerButtonEdit
      role="tab"
      :tabindex="
        dropdown.isOpen ? (modalStore.isOpen ? '-1' : contentIndex) : '-1'
      "
      @click="runAction('edit')"
      v-if="props.rights.canEdit"
      :class="[
        props.rights.canDelete || props.rights.canDownload ? '' : 'last',
      ]"
    />
    <FileManagerButtonDownload
      role="tab"
      :tabindex="
        dropdown.isOpen ? (modalStore.isOpen ? '-1' : contentIndex) : '-1'
      "
      @click="runAction('download')"
      v-if="props.rights.canDownload"
      :class="[props.rights.canDelete ? '' : 'last']"
    />
    <FileManagerButtonDelete
      role="tab"
      :tabindex="
        dropdown.isOpen ? (modalStore.isOpen ? '-1' : contentIndex) : '-1'
      "
      @click="runAction('delete')"
      v-if="props.rights.canDelete"
      class="last"
    />
  </div>
  <!-- end dropdown -->
</template>
