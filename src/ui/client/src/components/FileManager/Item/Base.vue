<script setup>
import { reactive, computed, defineProps, defineEmits, onMounted } from "vue";
import FileManagerItemDropdown from "@components/FileManager/Item/Dropdown.vue";
import FileManagerItemSvgFolder from "@components/FileManager/Item/Svg/Folder.vue";
import FileManagerItemSvgFile from "@components/FileManager/Item/Svg/File.vue";
import { contentIndex } from "@utils/tabindex.js";
import { useModalStore } from "@store/configs.js";

const modalStore = useModalStore();

// FileManagerBase can be a folder or file
// Case folder, emit the folder path on click to update display
// Emit on filemanager layout the value of buttons list @action
const props = defineProps({
  data: {
    type: Object,
    required: true,
  },
  rights: {
    type: Object,
    required: true,
  },
});

const itemID = computed(() => {
  return `${props.data.path}-${
    props.data.pathLevel
  }-${props.data.name.replaceAll("_", "-")}`;
});

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
  <div class="file-manager-item-container">
    <button
      :tabindex="modalStore.isOpen ? '-1' : contentIndex"
      class="file-manager-item-nav"
      @click="
        () => {
          if (props.data.type === 'folder') {
            return (modalStore.data.path = props.data.path);
          }
          return runAction('view');
        }
      "
      :aria-describedby="`${itemID}-text`"
    >
      <span class="sr-only" :id="`${itemID}-text`">
        {{ $t("custom_conf_path") }}
      </span>
      <FileManagerItemSvgFolder
        v-if="props.data.type === 'folder'"
        :path="props.data.path"
      />

      <FileManagerItemSvgFile v-if="props.data.type === 'file'" />

      <span
        :class="[
          props.data.path.length > 50
            ? 'xs'
            : props.data.path.length > 50
              ? 'sm'
              : 'base',
        ]"
        class="file-manager-item-name"
      >
        {{ props.data.name.replaceAll("_", "-") }}
      </span>
    </button>
    <FileManagerItemDropdown
      :id="itemID"
      :rights="props.rights"
      :data="props.data"
    />
  </div>
</template>
