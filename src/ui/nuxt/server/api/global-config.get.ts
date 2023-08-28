import { fetchApi, setResponse, response } from "../../utils/api";

import {
  getPluginsByContext,
  addConfToPlugins,
  setPluginsData,
} from "../../utils/plugins";

const resErr: response = {
  type: "error",
  status: 500,
  message: "Impossible to get global config",
  data: [],
};
// Get global config
export default defineEventHandler(async (event) => {
  let data: any, conf: any, plugins: any;

  // Get default config from core api
  conf = await fetchApi(
    "/config?methods=true&new_format=1",
    "GET",
    false,
    resErr
  );
  if (conf.type === "error") return await conf;

  // Get default plugins from core api
  plugins = await fetchApi("/plugins", "GET", false, resErr);
  if (conf.type === "error") return await plugins;

  // Format core api data
  try {
    const setPlugins = await setPluginsData(plugins.data);
    const mergeConf = await addConfToPlugins(setPlugins, conf.data["global"]);
    data = await getPluginsByContext(mergeConf, "global");
    return await setResponse("success", 200, "Get global config", data);
  } catch (err) {
    return resErr;
  }
});
