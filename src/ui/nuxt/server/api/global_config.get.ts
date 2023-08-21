import { getPluginsByContext, addConfToPlugins } from "../../utils/plugins";

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  let data, conf: any, plugins: [];
  try {
    conf = await $fetch(`/config?methods=true`, {
      baseURL: config.apiAddr,
      method: "GET",
      Headers: {
        Authorization: `Bearer ${config.apiToken}`,
      },
    });

    plugins = await $fetch(`/plugins`, {
      baseURL: config.apiAddr,
      method: "GET",
      Headers: {
        Authorization: `Bearer ${config.apiToken}`,
      },
    });

    const mergeConf = await addConfToPlugins(plugins, conf);
    data = await getPluginsByContext(mergeConf, "global");
  } catch (err) {
    data = Promise.reject(new Error("fail getting data"));
  }
  return await data;
});
