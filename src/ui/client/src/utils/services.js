// Filter services
export function getServicesByFilter(services, filters, details) {
  const result = {};
  for (const [key, plugins] of Object.entries(services)) {
    let isMatch = true;

    // Check keyword
    if (!filters.servName) isMatch = true;
    if (filters.servName && !key.includes(filters.servName)) {
      isMatch = false;
    }

    if (filters.servMethod !== "all") {
      plugins.forEach((plugin) => {
        if (plugin.id !== "general") return;
        const method = plugin.settings.SERVER_NAME.method;
        if (method !== filters.servMethod) isMatch = false;
      });
    }

    // Remove details with "all" filter
    const filteredDetails = details.filter(
      (detail) => filters[detail.id] !== "all"
    );

    console.log("filteredDetails", filteredDetails);

    filteredDetails.forEach((detail) => {
      plugins.forEach((plugin) => {
        if (plugin.id !== detail.id) return;
        console.log(plugin.settings[detail.setting].value, filters[detail.id]);
        const isSetting =
          plugin.settings[detail.setting].value === "yes" ? "true" : "false";
        if (isSetting !== filters[detail.id]) isMatch = false;
      });
    });

    result[key] = isMatch;
  }

  console.log(result);

  return result;
}

// Get methods
export function getServicesMethods(services) {
  const methods = [];
  for (const [key, plugins] of Object.entries(services)) {
    plugins.forEach((plugin) => {
      if (plugin.id !== "general") return;
      const method = plugin.settings.SERVER_NAME.method;
      if (!methods.includes(method)) methods.push(method);
    });
  }

  return methods;
}
