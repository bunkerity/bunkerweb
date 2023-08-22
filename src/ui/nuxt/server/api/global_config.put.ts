export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const body = await readBody(event);
  let data;
  try {
    data = await $fetch(`/config/global`, {
      baseURL: config.apiAddr,
      method: "PUT",
      Headers: {
        Authorization: `Bearer ${config.apiToken}`,
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    data = Promise.reject(new Error("fail getting data"));
  }
  return await data;
});
