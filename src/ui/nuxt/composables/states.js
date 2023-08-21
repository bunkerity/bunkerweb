// Global
export const useDarkMode = () => useState("darkMode", () => true);

// Plugins
export const useModes = () =>
  useState("modes", () => ["AUTOCONF_MODE", "SWARM_MODE", "KUBERNETES_MODE"]);
export const useDefaultMethod = () =>
  useState("defaultMethod", () => "default");
export const useMethodList = () =>
  useState("methodList", () => ["all", "ui", "default", "scheduler"]);

// Jobs page
export const useSuccessFilter = () => useState("successFilter", () => "all");
export const useEveryFilter = () => useState("everyFilter", () => "all");
export const useReloadFilter = () => useState("reloadFilter", () => "all");
export const useJobsKeyFilter = () => useState("jobsKeyFilter", () => "");

// Plugins page
export const usePluginKey = () => useState("pluginKey", () => "");
export const usePluginType = () => useState("pluginType", () => "all");

// Services or global_config page
export const useConf = () => {
  const conf = useState("conf", () => {});
  conf["global"] = {};
  conf["services"] = {};
  return conf;
};
