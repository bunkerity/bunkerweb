import { fetchApi, response } from "../../utils/api";

const resErr: response = {
  type: "error",
  status: 500,
  message: "Impossible to update global config",
  data: {},
};

const resOK: response = {
  type: "success",
  status: 200,
  message: "Updated global config",
  data: {},
};

export default defineEventHandler(async (event) => {
  // Update global config
  const body = await readBody(event);

  return await fetchApi("/config/global", "PUT", body, resOK, resErr);
});
