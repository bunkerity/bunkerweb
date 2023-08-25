export interface response {
  type: string;
  status: string | number;
  message: string;
  data: any;
}

// Setup response json
export async function setupResponse(
  res: response,
  type: string,
  status: string | number,
  message: string,
  data: any
) {
  res["type"] = type;
  res["status"] = status;
  res["message"] = message;
  res["data"] = data;
  return res;
}
