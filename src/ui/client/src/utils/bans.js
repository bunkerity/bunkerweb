// Filter bans
export function getBansByFilter(bans, filters) {
  bans.forEach((ban, id) => {
    let isMatch = true;

    if (filters.search && !ban.ip.includes(filters.search)) isMatch = false;
    if (filters.reason !== "all" && !ban.reason.includes(filters.reason))
      isMatch = false;

    ban["isMatchFilter"] = isMatch;
  });

  return bans;
}
