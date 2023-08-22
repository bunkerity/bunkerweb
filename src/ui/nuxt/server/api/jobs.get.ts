import { jobsFormat } from "../../utils/jobs";

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  let data;
  try {
    const jobs = await $fetch(`/jobs`, {
      baseURL: config.apiAddr,
      method: "GET",
      Headers: {
        Authorization: `Bearer ${config.apiToken}`,
      },
    });
    data = await jobsFormat(jobs);
  } catch (err) {
    data = Promise.reject(new Error("fail getting data"));
  }
  return data;
});
