import { defineStore } from "pinia";
import { ref } from "vue";

export const useModalStore = defineStore("fileManagerModal", () => {
  const isOpen = ref(false);
  const name = ref("");
  const data = ref({ type: "", action: "", path: "", value: "", method: "" });
  const submit = ref(false);

  function setOpen(bool) {
    isOpen.value = bool;
  }

  function setName(str) {
    name.value = str;
  }

  function setData(obj) {
    data.value = obj;
  }

  function setDataKey(key, val) {
    data.value[key] = val;
  }

  function resetSubmit() {
    submit.value = false;
  }

  function submitModal() {
    submit.value = true;
  }

  return {
    isOpen,
    name,
    data,
    submit,
    setOpen,
    setName,
    setData,
    setDataKey,
    resetSubmit,
    submitModal,
  };
});
