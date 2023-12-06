<script setup>
import { computed, defineProps, defineEmits } from "vue";

const props = defineProps({
  // Active path
  currPath: {
    type: String,
    required: true,
  },
});

// Get each part of a path
const pathSplit = computed(() => {
  return props.currPath.split("/").filter(String);
});

const emits = defineEmits(["updatePath"]);

// All paths are separated by slashes
// Split and pop the last one to get the prev path
function getPrevPath() {
  const split = props.currPath.split("/");
  // Case no prev path
  if (split.length < 2) return props.currPath;
  // Send prev path
  split.pop();
  return split.join("/");
}

// All paths are separated by slashes with a given id
// For example root/test => <id = 0>/<id = 1>
// Get click path by removing path with id > clickId
function getClickPath(id) {
  const split = props.currPath.split("/");
  for (let i = 0; split.length - 1 > id; i++) {
    split.pop();
  }
  return split.join("/");
}
</script>

<template>
  <ul
    :aria-description="$t('custom_conf_breadcrumb')"
    class="file-manager-breadcrumb"
  >
    <li class="file-manager-breadcrumb-back-btn">
      <button @click="$emit('updatePath', getPrevPath())">
        <svg
          class="file-manager-breadcrumb-back-svg"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="1.5"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3"
          />
        </svg>
      </button>
    </li>
    <li
      v-for="(item, id) in pathSplit"
      class="file-manager-breadcrumb-item"
      :aria-current="id === pathSplit.length - 1 ? 'true' : 'false'"
    >
      <button
        :aria-description="$t('custom_conf_breadcrumb_item_desc')"
        @click="$emit('updatePath', getClickPath(id))"
        type="button"
        class="file-manager-breadcrumb-item-btn"
      >
        {{ item === "root" ? "" : item }}
      </button>
    </li>
  </ul>
</template>
