export const useDarkMode = () => useState<boolean>("darkMode", () => true);
export const useModes = () =>
  useState<string[]>("modes", () => [
    "AUTOCONF_MODE",
    "SWARM_MODE",
    "KUBERNETES_MODE",
  ]);
