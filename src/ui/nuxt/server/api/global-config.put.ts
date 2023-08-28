import { fetchApi, response } from "../../utils/api";

const resErr: response = {
  type: "error",
  status: 500,
  message: "Impossible to update global config",
  data: {},
};

export default defineEventHandler(async (event) => {
  // Update global config
  const body = await readBody(event);

  return await fetchApi("/config/global", "PUT", body, resErr);
});
