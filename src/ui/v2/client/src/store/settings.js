import { defineStore } from "pinia";
import { ref } from "vue";

export const useConfigStore = defineStore("config", () => {
  const data = ref({ global: {}, services: {} });

  function updateConf(name, id, value) {
    if (!name || !id) return;

    if (name === "global") data.value[name][id] = value;
    if (name !== "global") {
      if (!(name in data.value["services"])) data.value["services"][name] = {};
      data.value["services"][name][id] = value;
    }
  }

  function $reset() {
    data.value = {
      global: {},
      services: {},
    };
  }

  return { data, $reset, updateConf };
});

export const useModesStore = defineStore("modes", () => {
  const data = ref(["AUTOCONF_MODE", "SWARM_MODE", "KUBERNETES_MODE"]);

  return { data, updateConf };
});
