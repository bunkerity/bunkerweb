from io import BytesIO
import tarfile

from logger import log

class ApiCaller :

    def __init__(self, apis=[]) :
        self.__apis = apis

    def _set_apis(self, apis) :
        self.__apis = apis

    def _get_apis(self) :
        return self.__apis

    def _send_to_apis(self, method, url, files=None, data=None, response=False) :
        ret = True
        for api in self.__apis :
            if files is not None :
                for file, buffer in files.items() :
                    buffer.seek(0, 0)
            sent, err, status, resp = api.request(method, url, files=files, data=data)
            if not sent :
                ret = False
                log("API", "❌", "Can't send API request to " + api.get_endpoint() + url + " : " + err)
            else :
                if status != 200 :
                    ret = False
                    log("API", "❌", "Error while sending API request to " + api.get_endpoint() + url + " : status = " + resp["status"] + ", msg = " + resp["msg"])
                else :
                    log("API", "ℹ️", "Successfully sent API request to " + api.get_endpoint() + url)
        if response :
            if isinstance(resp, dict) :
                return ret, resp
            return ret, resp.json()
        return ret

    def _send_files(self, path, url) :
        ret = True
        tgz = BytesIO()
        with tarfile.open(mode="w:gz", fileobj=tgz) as tf :
            tf.add(path, arcname=".")
        tgz.seek(0, 0)
        files = {"archive.tar.gz": tgz}
        if not self._send_to_apis("POST", url, files=files) :
            ret = False
        tgz.close()
        return ret
