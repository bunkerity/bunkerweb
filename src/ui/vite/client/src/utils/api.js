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
// state args must be reactive variable with isPend and isErr keys
export async function fetchAPI(
  api,
  method,
  body = false,
  state = null,
  addFeedback = null,
) {
  // Block scope state object if any passed to avoid error
  !state ? (state = { isPend: false, isErr: false, data: {} }) : false;
  // Fetch
  const baseURL = "http://localhost:8000";
  state.isPend = true;
  return await fetch(`${baseURL}${api}`, {
    method: method.toUpperCase(),
    headers: {
      Authorization: `Bearer ${""}`,
      "Content-Type": "application/json",
    },
    // Only when exist and possible
    ...(body &&
      method.toUpperCase() !== "GET" && { body: JSON.stringify(body) }),
  })
    .then((res) => {
      state.isPend = false;
      state.isErr = false;
      return res.json();
    })
    .then((data) => {
      state.data = JSON.parse(data["data"]);
      addFeedback
        ? addFeedback(data["type"], data["status"], data["message"])
        : false;
      return data;
    })
    .catch((err) => {
      state.isPend = false;
      state.isErr = true;
      state.data = {};
      addFeedback
        ? addFeedback(
            err["type"] || "error",
            err["status"] || 500,
            err["message"] || "Internal Server Error",
          )
        : false;
      // Set custom error data before throwing err
      return err;
    });
}
