export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const body = await readBody(event);
  let data;
  try {
    data = await $fetch(`/instances/${body["hostname"]}/${body["operation"]}`, {
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
