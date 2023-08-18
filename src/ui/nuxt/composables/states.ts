// Global
export const useDarkMode = () => useState<boolean>("darkMode", () => true);

// Plugins
export const useModes = () =>
  useState<string[]>("modes", () => [
    "AUTOCONF_MODE",
    "SWARM_MODE",
    "KUBERNETES_MODE",
  ]);

// Jobs page
export const useSuccess = () => useState<string>("success", () => "all");
export const useEvery = () => useState<string>("every", () => "all");
export const useReload = () => useState<string>("reload", () => "all");
export const useJobsKey = () => useState<string>("jobsKey", () => "");

// Plugins page
export const usePluginKey = () => useState<string>("pluginKey", () => "");
export const usePluginType = () => useState<string>("pluginType", () => "all");

// Services or global_config page
export const useSettingsKey = () => useState<string>("settingsKey", () => "");
