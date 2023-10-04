import { jobsFormat } from "../../utils/jobs";

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const body = await readBody(event);
  let data;
  try {
    data = await $fetch(`/jobs/${body["job-name"]}/run`, {
      baseURL: config.apiAddr,
      method: "POST",
      Headers: {
        Authorization: `Bearer ${config.apiToken}`,
      },
    });
  } catch (err) {
    data = Promise.reject(new Error("fail getting data"));
  }
  return data;
});
