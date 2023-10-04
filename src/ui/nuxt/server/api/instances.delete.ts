export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const body = await readBody(event);
  let data;
  try {
    data = await $fetch(`/instances/${body["hostname"]}`, {
      baseURL: config.apiAddr,
      method: "DELETE",
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
