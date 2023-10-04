// Global
export const useDarkMode = () => useState<boolean>("darkMode", () => true);

// Plugins
export const useModes = () =>
  useState<string[]>("modes", () => [
    "AUTOCONF_MODE",
    "SWARM_MODE",
    "KUBERNETES_MODE",
  ]);
export const useDefaultMethod = () =>
  useState<string>("defaultMethod", () => "default");
export const useMethodList = () =>
  useState<string[]>("methodList", () => ["all", "ui", "default", "scheduler"]);

// Jobs page
export const useIntervalList = () =>
  useState<string[]>("intervalList", () => [
    "all",
    "once",
    "hour",
    "day",
    "week",
  ]);

export const useSuccessFilter = () =>
  useState<string>("successFilter", () => "all");
export const useEveryFilter = () =>
  useState<string>("everyFilter", () => "all");
export const useReloadFilter = () =>
  useState<string>("reloadFilter", () => "all");
export const useJobsKeyFilter = () =>
  useState<string>("jobsKeyFilter", () => "");

// Plugins page
export const usePluginKey = () => useState<string>("pluginKey", () => "");
export const usePluginType = () => useState<string>("pluginType", () => "all");
