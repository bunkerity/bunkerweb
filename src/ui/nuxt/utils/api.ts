export interface response {
  type: string;
  status: string | number;
  message: string;
  data: any;
}

// Setup response json
export async function setResponse(
  type: string,
  status: string | number,
  message: string,
  data: any,
) {
  const res: response = { type: "", status: "", message: "", data: {} };

  res["type"] = type;
  res["status"] = status;
  res["message"] = message;
  res["data"] = data;
  return res;
}

// Fetch api
export async function fetchApi(
  api: string,
  method: any,
  body: any,
  resSuccess: response,
  resErr: response,
) {
  const defaultData: any = {};
  const config = useRuntimeConfig();
  const options = {
    baseURL: config.apiAddr,
    method: method.toUpperCase(),
    Headers: {
      Authorization: `Bearer ${config.apiToken}`,
    },
    // Only when exist and possible
    ...(body &&
      method.toUpperCase() !== "GET" && { body: JSON.stringify(body) }),
  };
  return await $fetch(api, options)
    .then((data: any) => {
      // Set info
      const type = resSuccess["type"] || "success";
      const status = resSuccess["status"] || 200;
      const message =
        method.toUpperCase() === "GET"
          ? resSuccess["message"] || `${method.toUpperCase()} ${api} succeed.`
          : data["message"] ||
            resSuccess["message"] ||
            `${method.toUpperCase()} ${api} succeed.`;
      const dataRes =
        method.toUpperCase() === "GET" ? data || defaultData : defaultData;

      return setResponse(type, status, message, dataRes);
    })
    .catch((err) => {
      // Set custom error data before throwing err
      return setResponse(
        resErr["type"] || "error",
        err.status || resErr["status"] || 500,
        err.data["message"] || resErr["message"] || `Internal Server Error`,
        resErr["data"] || defaultData,
      );
    });
}
