// Filter reports
export function getReportsByFilter(reports, filters) {
  reports.forEach((report, id) => {
    let isMatch = true;
    // Search filter
    if (
      (filters.search &&
        !report.title.toLowerCase().includes(filters.search.toLowerCase())) ||
      !report.description.toLowerCase().includes(filters.search.toLowerCase())
    )
      isMatch = false;

    // Select filters
    const selectFilters = ["country", "method", "status", "reason"];

    selectFilters.forEach((filter) => {
      if (
        filters[filter] !== "all" &&
        !report[filter].toLowerCase().includes(filters[filter].toLowerCase())
      )
        isMatch = false;
    });

    report["isMatchFilter"] = isMatch;
  });

  // Update reports
  return reports;
}

export function getSelectList(baseItems, loopArr, keyCheck) {
  const arr = baseItems;
  loopArr.forEach((item) => {
    if (arr.indexOf(item[keyCheck]) === -1) arr.push(item[keyCheck]);
  });
  return arr;
}
