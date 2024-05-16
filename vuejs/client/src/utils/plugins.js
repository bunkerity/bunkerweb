// Set additional data to plugins
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

    // Case not multiple, add direct custom value to setting
    Object.entries(settings).forEach(([settingName, settingData]) => {
      if (!("multiple" in settingData)) {
        try {
          settingData["value"] = config[settingName]["value"];
          settingData["method"] = config[settingName]["method"];
          delete config[settingName];
        } catch (err) {}
      }
    });

    // Case multiple, format on config is setting_num
    // Multiples need to add a setting next to base one
    // To avoid loop issue by adding a setting
    // We need to add them after loop
    const multiples = [];
    Object.entries(settings).forEach(([settingName, settingData]) => {
      if (!!("multiple" in settingData)) {
        // We need to look on config
        // When a base name match config custom multiple
        Object.entries(config).forEach(([multipleName, multipleData]) => {
          if (!multipleName.startsWith(settingName)) return;
          // Case match, add multiple
          // Using base multiple model
          const cloneSetting = JSON.parse(JSON.stringify(settingData));
          cloneSetting["value"] = multipleData["value"];
          cloneSetting["method"] = multipleData["method"];
          multiples.push({ [multipleName]: cloneSetting });
        });
      }
    });

    // Append custom multiple as regular settings
    // We may have only one custom setting on a group
    // We will fill empty settings from a group on settings multiple component logic
    for (let i = 0; i < multiples.length; i++) {
      const multSetting = multiples[i];
      const multName = Object.keys(multSetting).join();
      const multData = multSetting[multName];
      settings[multName] = multData;
    }
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

// Translate keys that support multiple languages
export function pluginI18n(plugins, lang, fallback) {
  plugins.forEach((plugin) => {
    // Main plugin info
    setLangOrFallback(plugin, "name", lang, fallback);
    setLangOrFallback(plugin, "description", lang, fallback);
    // Each settings info
    for (const [key, value] of Object.entries(plugin["settings"])) {
      setLangOrFallback(value, "help", lang, fallback);
      setLangOrFallback(value, "label", lang, fallback);
    }
  });
  return plugins;
}

function setLangOrFallback(obj, key, lang, fallback) {
  try {
    if (!!(lang in obj[key])) {
      obj[key] = obj[key][lang];
    }
  } catch (err) {}

  // Case didn't find lang, we will get fallback (english)
  try {
    if (!!(fallback in obj[key])) {
      obj[key] = obj[key][fallback];
    }
  } catch (err) {}
}

export function getRemainFromFilter(filterPlugins) {
  const remainPlugins = [];
  filterPlugins.forEach((item) => {
    item["isMatchFilter"] ? remainPlugins.push(item.name) : false;
  });
  return remainPlugins;
}
