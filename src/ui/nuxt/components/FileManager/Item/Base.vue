<script setup>
// FileManagerBase can be a folder or file
// Case folder, emit the folder path on click to update display
// Emit on filemanager layout the value of buttons list @action
const props = defineProps({
  type: {
    type: String,
    required: true,
  },
  path: {
    type: String,
    required: false,
  },
  value: {
    type: String,
    required: true,
  },
  canDelete: {
    type: Boolean,
    required: true,
  },
  canEdit: {
    type: Boolean,
    required: true,
  },
  canDownload: {
    type: Boolean,
    required: true,
  },
});

// Check if root path (not same svg) by slash numbers
const path = reactive({
  name: props.path.substring(props.path.lastIndexOf("/") + 1),
});

const emits = defineEmits(["updatePath", "action"]);
</script>

<template>
  <div class="file-manager-item-container">
    <button
      class="file-manager-item-nav"
      @click="props.type === 'folder' ? $emit('updatePath', props.path) : null"
    >
      <FileManagerItemSvgFolder
        v-if="props.type === 'folder'"
        :path="props.path"
      />
      <FileManagerItemSvgFile v-if="props.type === 'file'" />

      <span class="file-manager-item-name">
        {{ path.name }}
      </span>
    </button>
    <FileManagerItemDropdown
      @action="(v) => $emit('action', v)"
      :canEdit="props.canEdit"
      :canDelete="props.canDelete"
      :canDownload="props.canDownload"
    />
  </div>
</template>
