// Filter actions
export function getActionsByFilter(actions, filters) {
  actions.forEach((action, id) => {
    let isMatch = true;
    // Search filter
    if (
      (filters.search &&
        !action.title.toLowerCase().includes(filters.search.toLowerCase())) ||
      !action.description.toLowerCase().includes(filters.search.toLowerCase())
    )
      isMatch = false;
    // Method filter
    if (
      filters.method !== "all" &&
      !action.method.toLowerCase().includes(filters.method.toLowerCase())
    )
      isMatch = false;
    // Action api filter
    if (
      filters.actionApi !== "all" &&
      !action.api_method.toLowerCase().includes(filters.actionApi.toLowerCase())
    )
      isMatch = false;

    action["isMatchFilter"] = isMatch;
  });

  // Update actions
  return actions;
}

export function getSelectList(baseItems, loopArr, keyCheck) {
  const arr = baseItems;
  loopArr.forEach((item) => {
    if (arr.indexOf(item[keyCheck]) === -1) arr.push(item[keyCheck]);
  });
  return arr;
}
