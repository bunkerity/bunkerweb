// Filter actions
export function getLogsByFilter(actions, filters) {
  if (!Array.isArray(actions)) return [];

  actions.forEach((action, id) => {
    let isMatch = true;
    // Tags filter
    if (filters.tags.indexOf("all") === -1) {
      let oneTagMatch = false;
      for (let i = 0; i < action.tags.length; i++) {
        const tag = action.tags[i];
        if (filters.tags.indexOf(tag) !== -1) oneTagMatch = true;
      }
      isMatch = oneTagMatch ? isMatch : false;
    }

    action["isMatchFilter"] = isMatch;
  });

  // Update actions
  return actions;
}

// None limited list of tags
export function getTags() {
  return ["plugin", "job", "action", "instance", "config", "custom_config"];
}
