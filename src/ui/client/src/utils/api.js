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
  isJSON = true,
  fileName = null, // test.json (name +  extension)
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
      "Content-Type": isJSON ? "application/json" : "application/octet-stream",
      "X-CSRF-TOKEN": getCookie("csrf_access_token"),
    },
    // Only when exist and possible
    ...(body &&
      method.toUpperCase() !== "GET" && { body: JSON.stringify(body) }),
  })
    .then((res) => {
      state.isPend = false;
      state.isErr = false;
      // Can be a json or a file
      return isJSON ? res.json() : res.blob();
    })
    .then((data) => {
      // Case no JSON, we handle file download
      if (!isJSON) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a); // we need to append the element to the dom -> otherwise it will not work in firefox
        a.click();
        a.remove(); //afterwards we remove the element again
        return true;
      }

      if (isJSON) {
        state.isErr = data["type"] === "error" ? true : false;
        state.data = JSON.parse(
          typeof data["data"] === "string"
            ? data["data"]
            : JSON.stringify(data["data"]),
        );
        addFeedback
          ? addFeedback(data["type"], data["status"], data["message"])
          : false;
        return data;
      }
    })
    .catch((err) => {
      state.isPend = false;
      state.isErr = true;
      state.data = {};

      if (!isJSON) {
        addFeedback
          ? addFeedback(
              err["type"] || "error",
              err["status"] || 500,
              err["message"] ||
                "Internal Server Error, impossible to download file",
            )
          : false;
      }

      if (isJSON) {
        addFeedback
          ? addFeedback(
              err["type"] || "error",
              err["status"] || 500,
              err["message"] || "Internal Server Error, impossible to get JSON",
            )
          : false;
      }

      // Set custom error data before throwing err
      return err;
    });
}

export function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}
