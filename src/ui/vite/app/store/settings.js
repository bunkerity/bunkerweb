import { defineStore } from "pinia";

export const useConfigStore = defineStore("config", () => {
  const data = ref({ global: {}, services: {} });

  function updateConf(context, id, value) {
    if (!context || !id) return;
    data.value[context][id] = value;
  }

  return { data, updateConf };
});

export const useModesStore = defineStore("modes", () => {
  const data = ref(["AUTOCONF_MODE", "SWARM_MODE", "KUBERNETES_MODE"]);

  return { data, updateConf };
});
