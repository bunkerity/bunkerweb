export function getJobsIntervalList() {
  return ["all", "once", "hour", "day", "week"];
}

// Format to go from dict to array
export async function jobsFormat(jobs) {
  const jobsArr = [];

  Object.entries(jobs).forEach(([name, data]) => {
    jobsArr.push({ [name]: data });
  });

  return jobsArr;
}

// Get success number
export function getJobsSuccessNum(jobs) {
  let count = 0;
  jobs.forEach((job, id) => {
    const jobName = Object.keys(job).join();
    const data = job[jobName];
    if (data["history"][0]["success"]) count++;
  });
  return count;
}

// Get reload  number
export function getJobsReloadNum(jobs) {
  let count = 0;
  jobs.forEach((job, id) => {
    const jobName = Object.keys(job).join();
    const data = job[jobName];
    if (data["reload"]) count++;
  });
  return count;
}

// Format cache data for select
export function getJobsCacheNames(caches) {
  const names = [];
  caches.forEach((cache) => {
    names.push(cache["file_name"]);
  });
  return names;
}

// Filter plugins
export function getJobsByFilter(jobs, filters) {
  console.log(jobs);
  jobs.forEach((job, id) => {
    const jobName = Object.keys(job).join();
    const data = job[jobName];
    for (const [key, value] of Object.entries(filters)) {
      // Check specific cases
      if (
        (!(key in data) && key !== "name" && key !== "success") ||
        (key === "name" && value === "") ||
        value === "all"
      )
        continue;
      const checkType = typeof value;
      let isMatch = true;

      if (checkType === "string" && key === "name") {
        const filterValue = value.toLowerCase().trim();
        const checkValue = jobName.toLowerCase().trim();
        console.log("check name : " + filterValue + " " + checkValue);
        isMatch = checkValue.includes(filterValue) ? true : false;
      }

      if (checkType === "string" && key !== "name") {
        const filterValue = value.toLowerCase().trim();
        const checkValue = data[key].toLowerCase().trim();
        console.log("check every", filterValue, checkValue);
        isMatch = checkValue.includes(filterValue) ? true : false;
      }

      if (checkType === "boolean" && key === "success") {
        console.log("success : " + data["history"][0][key]);
        isMatch = value === data["history"][0][key] ? true : false;
      }

      if (checkType === "boolean" && key !== "success") {
        console.log("check reload");
        isMatch = value === data[key] ? true : false;
      }

      // Result
      if (!isMatch) delete jobs[id];
    }
  });

  // Update jobs removing empty index (deleted jobs)
  return jobs.filter(Object);
}
