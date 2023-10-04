import { fetchApi, response } from "../../utils/api";

const resErr: response = {
  type: "error",
  status: 500,
  message: "Impossible to get instances",
  data: {},
};

const resOK: response = {
  type: "success",
  status: 200,
  message: "Get instances",
  data: {},
};

export default defineEventHandler(async (event) => {
  return await fetchApi("/instances", "GET", false, resOK, resErr);
});
