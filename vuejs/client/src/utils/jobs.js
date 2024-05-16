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

// Format cache data for select
export function getJobsCacheNames(caches) {
  const names = [];
  caches.forEach((cache) => {
    names.push(cache["file_name"]);
  });
  return names;
}

// Format cache data for select
export function getServId(jobs, jobName, cacheName) {
  let servID;
  jobs.forEach((jobItem) => {
    for (const [jobN, job] of Object.entries(jobItem)) {
      if (jobN !== jobName) continue;
      for (const [key, value] of Object.entries(job["cache"])) {
        if (value["file_name"] !== cacheName) continue;
        servID = value["service_id"];
      }
    }
  });
  return servID;
}

// Filter plugins
export function getJobsByFilter(jobs, filters) {
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
        isMatch = checkValue.includes(filterValue) ? true : false;
      }

      if (checkType === "string" && key !== "name") {
        const filterValue = value.toLowerCase().trim();
        const checkValue = data[key].toLowerCase().trim();
        isMatch = checkValue.includes(filterValue) ? true : false;
      }

      if (checkType === "boolean" && key === "success") {
        isMatch = value === data["history"][0][key] ? true : false;
      }

      if (checkType === "boolean" && key !== "success") {
        isMatch = value === data[key] ? true : false;
      }

      // Result
      if (!isMatch) delete jobs[id];
    }
  });

  // Update jobs removing empty index (deleted jobs)
  return jobs.filter(Object);
}
