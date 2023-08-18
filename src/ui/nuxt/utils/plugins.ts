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
      const isContext = data["context"] === context ? true : false;
      console.log(isContext);
      if (!isContext) delete settings[setting];
    });

    // Case no setting remaining, remove plugin
    if (Object.keys(plugin["settings"]).length === 0) delete plugins[id];
  });

  // Update plugins removing empty index (deleted plugins)
  return plugins.filter(Object);
}

// Keep only multiple settings for each plugins
export function getPluginsMultiple(plugins: []): object[] {
  plugins.forEach((plugin) => {
    const settings = plugin["settings"];

    Object.entries(settings).forEach(([setting, data]: [string, any]) => {
      // Remove settings that aren't multiple
      if (!("multiple" in data)) delete settings[setting];
    });
  });

  return plugins;
}

// For each plugins, loop on settings
// Get the number of different multiple names
// Move multiple settings from plugin.settings to plugin.multiples
// Every settings is order by multiple name like plugin.multiples.name = {settings}
export function setPluginsMultipleList(plugins: []): object[] {
  const multiplesName: string[] = [];

  plugins.forEach((plugin: any) => {
    const settings = plugin["settings"];

    Object.entries(settings).forEach(([setting, data]: [string, any]) => {
      // Remove settings that aren't multiple
      if (!!("multiple" in data)) {
        const multipleName = data["multiple"];
        multiplesName.includes(multipleName)
          ? true
          : multiplesName.push(multipleName);
      }
    });

    // Case no multiple on plugin, stop here
    if (multiplesName.length === 0) return;

    // Case multiple, create plugin.multiple dict to order them
    if (!("multiples" in plugin)) plugin["multiples"] = {};
    // Order them by name
    multiplesName.forEach((name) => {
      // Create plugin.multiple.name
      if (!(name in plugin["multiples"])) plugin["multiples"][name] = {};
      // Add settings that match the name and remove them from initial place
      Object.entries(settings).forEach(([setting, data]: [string, any]) => {
        if (!!("multiple" in data) && data["multiple"] === name) {
          plugin["multiples"][name][setting] = data;
          delete plugin["settings"][setting];
        }
      });
    });
  });

  return plugins;
}
