import { response, setupResponse } from "../../utils/api";
import {
  getPluginsByContext,
  addConfToPlugins,
  setPluginsData,
} from "../../utils/plugins";

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  let data: any, conf: any, plugins: any;
  const res: response = { type: "", status: "", message: "", data: null };
  try {
    conf = await $fetch(`/config?methods=true&new_format=1`, {
      baseURL: config.apiAddr,
      method: "GET",
      Headers: {
        Authorization: `Bearer ${config.apiToken}`,
      },
    }).catch((err) => {
      setupResponse(res, "error", err.status, err.data["message"], []);
    });

    plugins = await $fetch(`/plugins`, {
      baseURL: config.apiAddr,
      method: "GET",
      Headers: {
        Authorization: `Bearer ${config.apiToken}`,
      },
    }).catch((err) => {
      setupResponse(res, "error", err.status, err.data["message"], []);
    });

    const setPlugins = await setPluginsData(plugins);
    const mergeConf = await addConfToPlugins(setPlugins, conf);
    data = await getPluginsByContext(mergeConf, "global");
    return await setupResponse(res, "success", 200, "", data);
  } catch (err) {
    return res;
  }
});
