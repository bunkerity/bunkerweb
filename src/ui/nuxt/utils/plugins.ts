interface config {
  [key: string]: string;
}

interface multiples {
  [key: string]: {
    [key: string]: object;
  };
}

// We want to add config data as value of settings of plugins
export function addConfToPlugins(plugins: [], config: config): [] {
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
export function getSettingsSimple(settings: any): object {
  Object.entries(settings).forEach(([setting, data]: [string, any]) => {
    // Remove settings that are multiple
    if (!!("multiple" in data)) delete settings[setting];
  });
  return settings;
}

// Keep only multiple settings for specific plugin
export function getSettingsMultiple(settings: any): object {
  Object.entries(settings).forEach(([setting, data]: [string, any]) => {
    // Remove settings that aren't multiple
    if (!("multiple" in data)) delete settings[setting];
  });
  return settings;
}

// For a specific plugin, loop on settings
// Get the number of different multiple names
// Move multiple settings from plugin.settings to plugin.multiples
// Every settings is order by multiple name like plugin.multiples.name = {settings}
export function getSettingsMultipleList(settings: any): object | boolean {
  // Check to keep only multiple settings
  const multipleSettings = getSettingsMultiple(settings);

  // Case no multiple settings
  if (Object.keys(multipleSettings).length === 0) return false;

  // Case multiple, create list from this
  const multiples: multiples = {};
  const multiplesName: string[] = [];

  // Get number of multiple group by name
  Object.entries(multipleSettings).forEach(([setting, data]: [string, any]) => {
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
    Object.entries(settings).forEach(([setting, data]: [string, any]) => {
      if (!!("multiple" in data) && data["multiple"] === name) {
        multiples[name][setting] = data;
      }
    });
  });

  return multiples;
}
