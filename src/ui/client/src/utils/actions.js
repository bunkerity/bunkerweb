// Filter actions
export function getActionsByFilter(actions, filters) {
  actions.forEach((action, id) => {
    let isMatch = true;

    if (
      (filters.search && !action.title.includes(filters.search)) ||
      !action.text.includes(filters.search)
    )
      isMatch = false;
    if (filters.method !== "all" && !action.method.includes(filters.method))
      isMatch = false;

    action["isMatchFilter"] = isMatch;
  });

  // Update actions
  return actions;
}
