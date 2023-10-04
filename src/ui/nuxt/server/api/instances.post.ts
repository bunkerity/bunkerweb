export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const body = await readBody(event);
  let data;
  try {
    data = await $fetch(`/instances`, {
      baseURL: config.apiAddr,
      method: "POST",
      Headers: {
        Authorization: `Bearer ${config.apiToken}`,
      },
      body: body,
    });
  } catch (err) {
    data = Promise.reject(new Error("fail getting data"));
  }
  return data;
});
