// Setup response json
export async function setResponse(type, status, message, data) {
  const res = { type: "", status: "", message: "", data: {} };

  res["type"] = type;
  res["status"] = status;
  res["message"] = message;
  res["data"] = data;
  return res;
}

// Fetch api
export async function fetchAPI(api, method, body = false, pendState, errState) {
  const baseURL = "http://localhost:1337";
  pendState = true;

  return await fetch(`${baseURL}${api}`, {
    method: method.toUpperCase(),
    Headers: {
      Authorization: `Bearer ${""}`,
    },
    // Only when exist and possible
    ...(body &&
      method.toUpperCase() !== "GET" && { body: JSON.stringify(body) }),
  })
    .then((data) => {
      pendState = false;
      errState = false;

      // Set info
      const type = resSuccess["type"] || "success";
      const status = resSuccess["status"] || 200;
      const message =
        method.toUpperCase() === "GET"
          ? resSuccess["message"] || `${method.toUpperCase()} ${api} succeed.`
          : data["message"] ||
            resSuccess["message"] ||
            `${method.toUpperCase()} ${api} succeed.`;
      const dataRes = method.toUpperCase() === "GET" ? data || {} : {};

      return setResponse(type, status, message, dataRes);
    })
    .catch((err) => {
      pendState = false;
      errState = true;
      // Set custom error data before throwing err
      return setResponse(
        "error",
        err.status || 500,
        err.data?.message || `Internal Server Error`,
        {}
      );
    });
}
