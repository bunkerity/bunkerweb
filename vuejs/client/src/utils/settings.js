export function getModes() {
  return ["AUTOCONF_MODE", "SWARM_MODE", "KUBERNETES_MODE"];
}

export function getMethodList() {
  return ["all", "ui", "default", "scheduler"];
}

export function getDefaultMethod() {
  return "default";
}

// Filter plugins by settings
export function getSettingsByFilter(plugins, filters) {
  plugins.forEach((plugin, id) => {
    const settings = plugin["settings"];
    // We will check if all settings failed to determine plugin display
    const settingsNum = Object.keys(settings).length;
    let noMatchCount = 0;

    Object.entries(settings).forEach(([setting, data]) => {
      // Check if setting match
      let isMatch = true;
      // Look for every filter

      for (const [key, value] of Object.entries(filters)) {
        // Case one filter already fail
        if (!isMatch) continue;

        // Case nothing to check
        if ((!(key in data) && key !== "keyword") || value === "all") {
          settings[setting]["isMatchFilter"] = true;
          continue;
        }
        const checkType = typeof value;

        // Case filter is string like input or select
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
          // Case individual filter like method
          if (key !== "keyword") {
            const settingValue = data[key].toLowerCase().trim();

            isMatch = settingValue.includes(filterValue) ? true : false;
          }
        }

        // Case filter is checkbox-like
        if (checkType === "boolean") {
          isMatch = data[key] === value ? true : false;
        }
      }

      // After every filter check
      settings[setting]["isMatchFilter"] = isMatch;
      isMatch ? true : noMatchCount++;
    });

    // Case no settings match, hide plugin
    plugin["isMatchFilter"] = settingsNum === noMatchCount ? false : true;
  });

  // Update plugins removing empty index (deleted plugins)
  return plugins;
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

  // Case multiple, create better list
  const multiples = {};
  const multGroups = {};

  // Get group names and base data
  // Match only when end by _num
  const regex = new RegExp(/(_\d*).$/gm);

  Object.entries(multipleSettings).forEach(([setting, data]) => {
    if (!!("multiple" in data)) {
      // Add name group if doesn't exist
      const multName = data["multiple"];
      if (!(multName in multGroups)) multGroups[multName] = {};
      // Add setting if base one
      const suffix =
        setting.match(regex) === null ? null : setting.match(regex).join();
      // Case base
      if (!suffix && !("base" in multGroups[multName]))
        multGroups[multName]["base"] = {};
      if (!suffix) return (multGroups[multName]["base"][setting] = data);
      const suffixNum = suffix.replace("_", "");
      if (suffix && !(suffixNum in multGroups[multName]))
        multGroups[multName][suffixNum] = {};
      if (suffix) multGroups[multName][suffixNum][setting] = data;
    }
  });

  // Case no multiple group
  if (multGroups.length === 0) return false;

  // Some group can have only few settings custom
  // We have to fill missing settings using base data
  Object.entries(multGroups).forEach(([groupName, groupSettings]) => {
    // Base to compare
    const baseSettings = groupSettings["base"];
    const baseLength = Object.keys(baseSettings).length;

    Object.entries(groupSettings).forEach(([settingName, settings]) => {
      // Stop if base itself or already fill
      if (settingName === "base" || Object.keys(settings).length === baseLength)
        return;
      // Else, check for every setting if exist, if not create it
      Object.entries(settings).forEach(([settingName, data]) => {
        const suffix = settingName.match(regex).join();
        Object.entries(baseSettings).forEach(
          ([baseSettingName, baseSettingData]) => {
            // Case setting match base
            if (settingName.startsWith(baseSettingName)) return;
            // Case not, create
            settings[`${baseSettingName}${suffix}`] = baseSettingData;
          },
        );
      });
    });
  });

  return multGroups;
}
