<script setup>
import { computed } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import { useModalStore } from "@store/configs.js";

const modalStore = useModalStore();

// Get each part of a path
const pathSplit = computed(() => {
  return modalStore.data.path.split("/").filter(String);
});

// All paths are separated by slashes
// Split and pop the last one to get the prev path
function getPrevPath() {
  const split = modalStore.data.path.split("/");
  // Case no prev path
  if (split.length < 2) return modalStore.data.path;
  // Send prev path
  split.pop();
  return split.join("/");
}

// All paths are separated by slashes with a given id
// For example root/test => <id = 0>/<id = 1>
// Get click path by removing path with id > clickId
function getClickPath(id) {
  const split = modalStore.data.path.split("/");
  for (let i = 0; split.length - 1 > id; i++) {
    split.pop();
  }
  return split.join("/");
}
</script>

<template>
  <ul
    role="tablist"
    :aria-description="$t('custom_conf_breadcrumb')"
    class="file-manager-breadcrumb"
  >
    <li role="tab" class="file-manager-breadcrumb-back-btn">
      <button
        :tabindex="contentIndex"
        aria-describedby="file-manager-breadcrumb-back-btn-text"
        @click="modalStore.data.path = getPrevPath()"
      >
        <span id="file-manager-breadcrumb-back-btn-text" class="sr-only">
          {{ $t("custom_conf_breadcrumb_back_desc") }}
        </span>
        <svg
          role="img"
          aria-hidden="true"
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
      role="tab"
      v-for="(item, id) in pathSplit"
      class="file-manager-breadcrumb-item"
      :aria-current="id === pathSplit.length - 1 ? 'true' : 'false'"
    >
      <button
        :tabindex="contentIndex"
        :aria-description="$t('custom_conf_breadcrumb_item_desc')"
        @click="modalStore.data.path = getClickPath(id)"
        class="file-manager-breadcrumb-item-btn"
      >
        {{ item === "root" ? "root" : item.replaceAll("_", "-") }}
      </button>
    </li>
  </ul>
</template>
