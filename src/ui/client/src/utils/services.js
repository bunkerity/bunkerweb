// Filter services
export function getServicesByFilter(services, filters) {
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

    result[key] = isMatch;
  }

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
