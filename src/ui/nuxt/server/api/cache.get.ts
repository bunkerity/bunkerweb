import { jobsFormat } from "../../utils/jobs";

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const query = getQuery(event);
  let data;
  try {
    data = await $fetch(
      `/jobs/${query["job-name"]}/cache/${query["file-name"]}`,
      {
        baseURL: config.apiAddr,
        method: "GET",
        Headers: {
          Authorization: `Bearer ${config.apiToken}`,
        },
      },
    );
  } catch (err) {
    data = Promise.reject(new Error("fail getting data"));
  }
  return data;
});
