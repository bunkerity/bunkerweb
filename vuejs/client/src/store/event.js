import { data } from "autoprefixer";
import { defineStore } from "pinia";
import { ref } from "vue";

/**
  @name useEventStore
  @description Store to share data between components related to events (click, change, ...).
  We can toggle a component visibility, change a value, etc... using this store.
  Be aware that this store better work using primitive values (string, number, boolean) and not objects.
*/
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
