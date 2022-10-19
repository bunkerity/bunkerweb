from io import BytesIO
from os import environ
from tarfile import open as taropen

from logger import setup_logger


class ApiCaller:
    def __init__(self, apis=[]):
        self.__apis = apis
        self.__logger = setup_logger("Api", environ.get("LOG_LEVEL", "INFO"))

    def _set_apis(self, apis):
        self.__apis = apis

    def _get_apis(self):
        return self.__apis

    def _send_to_apis(self, method, url, files=None, data=None):
        ret = True
        for api in self.__apis:
            if files is not None:
                for buffer in files.values():
                    buffer.seek(0, 0)
            sent, err, status, resp = api.request(method, url, files=files, data=data)
            if not sent:
                ret = False
                self.__logger.error(
                    f"Can't send API request to {api.get_endpoint()}{url} : {err}",
                )
            else:
                if status != 200:
                    ret = False
                    self.__logger.error(
                        f"Error while sending API request to {api.get_endpoint()}{url} : status = {resp['status']}, msg = {resp['msg']}",
                    )
                else:
                    self.__logger.info(
                        f"Successfully sent API request to {api.get_endpoint()}{url}",
                    )
        return ret

    def _send_files(self, path, url):
        ret = True
        tgz = BytesIO()
        with taropen(mode="w:gz", fileobj=tgz) as tf:
            tf.add(path, arcname=".")
        tgz.seek(0, 0)
        files = {"archive.tar.gz": tgz}
        if not self._send_to_apis("POST", url, files=files):
            ret = False
        tgz.close()
        return ret
