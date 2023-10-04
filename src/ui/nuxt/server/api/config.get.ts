export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  let data;
  try {
    data = await $fetch(`/config`, {
      baseURL: config.apiAddr,
      method: "GET",
      Headers: {
        Authorization: `Bearer ${config.apiToken}`,
      },
    });
  } catch (err) {
    data = Promise.reject(new Error("fail getting data"));
  }
  return data;
});
