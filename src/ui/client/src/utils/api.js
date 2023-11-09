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
  addFeedback = null
) {
  // Block scope state object if any passed to avoid error
  !state ? (state = { isPend: false, isErr: false, data: {} }) : false;
  // Fetch
  // const baseURL = "http://localhost:7000"; // ? for dev
  const baseURL = window.location.origin; // ? for prod
  state.isPend = true;

  return await fetch(`${baseURL}${api}`, {
    method: method.toUpperCase(),
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-TOKEN": getCookie("csrf_access_token"),
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
      state.isErr = data["type"] === "error" ? true : false;
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
            err["message"] || "Internal Server Error"
          )
        : false;
      // Set custom error data before throwing err
      return err;
    });
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}
