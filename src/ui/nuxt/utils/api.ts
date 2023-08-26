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
  data: any
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
  baseUrl: string,
  api: string,
  method: any,
  auth: string,
  defaultData: any = {}
) {
  return await $fetch(api, {
    baseURL: baseUrl,
    method: method,
    Headers: {
      Authorization: auth,
    },
  })
    .then((data: any) => {
      if (method !== "GET")
        return setResponse(
          "success",
          200,
          data["message"] || `${method} /${api} succeed.`,
          defaultData
        );

      if (method === "GET")
        return setResponse(
          "success",
          200,
          `${method} /${api} succeed.`,
          data || defaultData
        );
    })
    .catch((err) => {
      return setResponse(
        "error",
        err.status || 500,
        err.data["message"] || `${method} /${api} succeed.`,
        defaultData
      );
    });
}
