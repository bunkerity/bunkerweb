interface config {
  [key: string]: string;
}

// We want to add config data as value of settings of plugins
export function addConfToPlugin(plugins: [], config: config): [] {
  plugins.forEach((plugin) => {
    const settings = plugin["settings"];

    Object.entries(settings).forEach(([setting, data]: [string, any]) => {
      // Add config value to config when match
      if (!!(setting in config)) {
        data["value"] = config[setting];
      }
      // Remove config value if matched (performance)
      try {
        delete config[setting];
      } catch (err) {}
    });
  });
  return plugins;
}

// We want to remove settings that not match context
// Or even entire plugin if all his settings not match context
export function getPluginsByContext(plugins: [], context: string): object[] {
  plugins.forEach((plugin, id) => {
    const settings = plugin["settings"];

    Object.entries(settings).forEach(([setting, data]: [string, any]) => {
      // Remove settings that not match context
      const isContect = data["context"] === context ? true : false;
      console.log(isContect);
      if (!isContect) delete settings[setting];
    });

    // Case no setting remaining, remove plugin
    if (Object.keys(plugin["settings"]).length === 0) delete plugins[id];
  });

  // Update plugins removing empty index (deleted plugins)
  return plugins.filter(Object);
}
