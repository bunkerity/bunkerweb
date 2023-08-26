import { fetchApi, setResponse } from "../../utils/api";
import {
  getPluginsByContext,
  addConfToPlugins,
  setPluginsData,
} from "../../utils/plugins";

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const auth = `Bearer ${config.apiToken}`;
  let data: any, conf: any, plugins: any;

  // Get default config from core api
  try {
    conf = await fetchApi(
      config.apiAddr,
      "/config?methods=true&new_format=1",
      "GET",
      auth
    );
  } catch (err) {
    return await conf;
  }

  // Get default plugins from core api
  try {
    plugins = await fetchApi(config.apiAddr, "/plugins", "GET", auth);
  } catch (err) {
    return await plugins;
  }

  // Format core api data
  try {
    const setPlugins = await setPluginsData(plugins.data);
    const mergeConf = await addConfToPlugins(setPlugins, conf.data["global"]);
    data = await getPluginsByContext(mergeConf, "global");
    return await setResponse("success", 200, "", data);
  } catch (err) {
    return setResponse(
      "error",
      500,
      "Error while formatting plugins and config to get global config.",
      []
    );
  }
});
