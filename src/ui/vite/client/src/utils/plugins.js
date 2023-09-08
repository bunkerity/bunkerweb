// Set additionnal data to plugins
export function setPluginsData(plugins) {
  plugins.forEach((plugin) => {
    const settings = plugin["settings"];
    // Replace some settings data
    Object.entries(settings).forEach(([setting, data]) => {
      // Add default method for filter
      if (!("method" in data)) data["method"] = "default";
    });
  });

  return plugins;
}

// We want to add config data as value of settings of plugins
export function addConfToPlugins(plugins, config) {
  plugins.forEach((plugin) => {
    const settings = plugin["settings"];

    Object.entries(settings).forEach(([setting, data]) => {
      // Add config value to config when match
      try {
        data["value"] = config[setting]["value"];
        data["method"] = config[setting]["method"];
        delete config[setting];
      }catch(err) {

      }
     
    });
  });

  return plugins;
}

// We want to remove settings that not match context
// Or even entire plugin if all his settings not match context
export function getPluginsByContext(plugins, context) {
  plugins.forEach((plugin, id) => {
    const settings = plugin["settings"];

    Object.entries(settings).forEach(([setting, data]) => {
      // Remove settings that not match context
      const isContext = data["context"] === context ? true : false;
      if (!isContext) delete settings[setting];
    });

    // Case no setting remaining, remove plugin
    if (Object.keys(plugin["settings"]).length === 0) delete plugins[id];
  });

  // Update plugins removing empty index (deleted plugins)
  return plugins.filter(Object);
}

// Filter plugins
export function getPluginsByFilter(plugins, filters) {
  plugins.forEach((plugin, id) => {
    for (const [key, value] of Object.entries(filters)) {
      // Case no key to check
      if (!(key in plugin) || value === "all") continue;
      const checkType = typeof value;
      let isMatch = true;

      if (checkType === "string") {
        const filterValue = value.toLowerCase().trim();
        const checkValue = plugin[key].toLowerCase().trim();
        isMatch = checkValue.includes(filterValue) ? true : false;
      }

      if (checkType === "boolean") {
        isMatch = value === plugin[key] ? true : false;
      }

      // Result
      if (!isMatch) plugins[id] = "";
    }
  });

  // Update plugins removing empty index (deleted plugins)
  return plugins.filter(String);
}
