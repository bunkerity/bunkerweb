import { data } from "autoprefixer";
import { defineStore } from "pinia";
import { ref } from "vue";

// This store allow to share data between components related to events
// For example, a click button event can create and store a value in this store to be use in another component

export const useEventStore = defineStore("event", () => {
  const event = ref({});

  // add only if the event is not already in the store
  function addEvent(name, value) {
    if (!(name in event.value)) event.value[name] = value;
  }

  function updateEvent(name, value) {
    event.value[name] = value;
  }

  function getEvent(name) {
    return event.value[name];
  }

  function deleteEvent(name) {
    delete event.value[name];
  }

  function $reset() {
    data.value = {};
  }

  return { event, $reset, addEvent, updateEvent, deleteEvent, getEvent };
});
