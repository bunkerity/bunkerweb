import { defineStore } from "pinia";
import { ref } from "vue";
export const useFeedbackStore = defineStore("feedback", () => {
  const data = ref([]);
  let feedID = 0;

  async function addFeedback(type, status, message) {
    feedID++;
    data.value.push({
      id: feedID,
      isNew: true,
      type: type,
      status: status,
      message: message,
    });
  }

  function removeFeedback(id) {
    data.value.splice(
      data.value.findIndex((item) => item["id"] === id),
      1
    );
  }

  return { data, addFeedback, removeFeedback };
});

export default useFeedbackStore;
