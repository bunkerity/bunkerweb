// Set additionnal data to plugins
export async function setPluginsData(plugins) {
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
export async function addConfToPlugins(plugins, config) {
  plugins.forEach((plugin) => {
    const settings = plugin["settings"];

    Object.entries(settings).forEach(([setting, data]) => {
      // Add config value to config when match
      for (const [confName, confData] of Object.entries(config)) {
        if (!!(setting in confData)) {
          data["value"] = confData["value"];
          if (!!("method" in data)) data["method"] = confData["method"];
          if (!("method" in data)) data["method"] = "default";
          // Remove config value if matched (performance)
          try {
            delete config[setting];
          } catch (err) {}
        }
      }
    });
  });

  return plugins;
}

// We want to remove settings that not match context
// Or even entire plugin if all his settings not match context
export async function getPluginsByContext(plugins, context) {
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

// Keep only simple settings for specific plugin
export function getSettingsSimple(settings) {
  Object.entries(settings).forEach(([setting, data]) => {
    // Remove settings that are multiple
    if (!!("multiple" in data)) delete settings[setting];
  });
  return settings;
}

// Keep only multiple settings for specific plugin
export function getSettingsMultiple(settings) {
  Object.entries(settings).forEach(([setting, data]) => {
    // Remove settings that aren't multiple
    if (!("multiple" in data)) delete settings[setting];
  });
  return settings;
}

// For a specific plugin, loop on settings
// Get the number of different multiple names
// Move multiple settings from plugin.settings to plugin.multiples
// Every settings is order by multiple name like plugin.multiples.name = {settings}
export function getSettingsMultipleList(settings) {
  // Check to keep only multiple settings
  const multipleSettings = getSettingsMultiple(settings);

  // Case no multiple settings
  if (Object.keys(multipleSettings).length === 0) return false;

  // Case multiple, create list from this
  const multiples = {};
  const multiplesName = [];

  // Get number of multiple group by name
  Object.entries(multipleSettings).forEach(([setting, data]) => {
    if (!!("multiple" in data)) {
      const multipleName = data["multiple"];
      multiplesName.includes(multipleName)
        ? true
        : multiplesName.push(multipleName);
    }
  });

  // Case no multiple group found
  if (multiplesName.length === 0) return false;

  // Case multiple group, order them by multiples.name
  multiplesName.forEach((name) => {
    // Create plugin.multiple.name
    if (!(name in multiples)) multiples[name] = {};
    // Add settings that match the name and remove them from initial place
    Object.entries(settings).forEach(([setting, data]) => {
      if (!!("multiple" in data) && data["multiple"] === name) {
        multiples[name][setting] = data;
      }
    });
  });

  return multiples;
}

// Filter plugins by settings
export function getSettingsByFilter(plugins, filters) {
  plugins.forEach((plugin, id) => {
    const settings = plugin["settings"];

    Object.entries(settings).forEach(([setting, data]) => {
      // Remove settings that don't match filter
      for (const [key, value] of Object.entries(filters)) {
        // Case no key to check
        if ((!(key in data) && key !== "keyword") || value === "all") continue;
        let isMatch = true;
        const checkType = typeof value;

        if (checkType === "string") {
          const filterValue = value.toLowerCase().trim();
          // Case keyword filter, check multiple keys
          if (key === "keyword") {
            const label = !!("label" in data)
              ? data["label"].toLowerCase().trim()
              : "";
            const help = !!("help" in data)
              ? data["help"].toLowerCase().trim()
              : "";
            isMatch =
              label.includes(filterValue) || help.includes(filterValue)
                ? true
                : false;
          }
          // Case individual filter
          if (key !== "keyword") {
            const settingValue = data[key].toLowerCase().trim();
            isMatch = settingValue.includes(filterValue) ? true : false;
          }
        }

        if (checkType === "boolean") {
          isMatch = data[key] === value ? true : false;
        }

        // Result
        if (!isMatch) delete settings[setting];
      }
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
