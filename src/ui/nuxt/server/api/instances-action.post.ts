export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const body = await readBody(event);
  let data;
  try {
    data = await $fetch(
      `${config.apiAddr}/instances/${body["hostname"]}/${body["operation"]}`,
      {
        method: "POST",
        Headers: {
          Authorization: `Bearer ${config.apiToken}`,
        },
      }
    );
  } catch (err) {
    data = Promise.reject(new Error("fail getting data"));
  }
  return data;
});
