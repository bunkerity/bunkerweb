import { defineStore } from "pinia";
import { ref } from "vue";

export const useLogsStore = defineStore("logs", () => {
  const tags = ref([]);

  function setTags(arr) {
    tags.value = arr;
  }

  function $reset() {
    tags.value = [];
  }

  return { tags, $reset, setTags };
});
