from requests import request


class API:
    def __init__(self, endpoint, host="bwapi"):
        self.__endpoint = endpoint
        self.__host = host

    def get_endpoint(self):
        return self.__endpoint

    def get_host(self):
        return self.__host

    def request(self, method, url, data=None, files=None, timeout=(10, 30)):
        try:
            headers = {}
            headers["User-Agent"] = "bwapi"
            headers["Host"] = self.__host
            if type(data) is dict:
                resp = request(
                    method,
                    f"{self.__endpoint}{url}",
                    json=data,
                    timeout=timeout,
                    headers=headers,
                )
            elif type(data) is bytes:
                resp = request(
                    method,
                    f"{self.__endpoint}{url}",
                    data=data,
                    timeout=timeout,
                    headers=headers,
                )
            elif files is not None:
                resp = request(
                    method,
                    f"{self.__endpoint}{url}",
                    files=files,
                    timeout=timeout,
                    headers=headers,
                )
            elif data is None:
                resp = request(
                    method, f"{self.__endpoint}{url}", timeout=timeout, headers=headers
                )
            else:
                return False, "unsupported data type", None, None
        except Exception as e:
            return False, str(e), None, None
        return True, "ok", resp.status_code, resp.json()
