from Job import Job

from logger import log

class SelfSignedCert(Job) :

	def __init__(self, redis_host=None, copy_cache=False, dst_cert="/etc/nginx/default-cert.pem", dst_key="/etc/nginx/default-key.pem", expiry="999", subj="CN=www.example.com") :
		name = "self-signed-cert"
		data = ["openssl", "req", "-nodes", "-x509", "-newkey", "rsa:4096", "-keyout", dst_key, "-out", dst_cert, "-days", expiry, "-subj", subj]
		type = "exec"
		self.__dst_cert = dst_cert
		self.__dst_key = dst_key
		super().__init__(name, data, filename=None, redis_host=redis_host, type=type, copy_cache=copy_cache)

	def _callback(self, success) :
		if success :
			log("self-signed-cert", "INFO", "generated certificate " + self.__dst_cert + " with private key " + self.__dst_key)
		else :
			log("self-signed-cert", "ERROR", "can't generate certificate " + self.__dst_cert + " with private key " + self.__dst_key)

