export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  let data;
  try {
    data = await $fetch(`/jobs`, {
      baseURL: config.apiCore,
      method: "GET",
    });
  } catch (err) {
    data = Promise.reject(new Error("fail getting data"));
  }
  return data;
});
