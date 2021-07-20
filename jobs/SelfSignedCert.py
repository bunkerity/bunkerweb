from Job import Job

class SelfSignedCert(Job) :

	def __init__(self, redis_host=None, copy_cache=False, dst_cert="/etc/nginx/default-cert.pem", dst_key="/etc/nginx/default-key.pem", expiry="999", subj="CN=www.example.com") :
		name = "self-signed-cert"
		data = ["openssl", "req", "-nodes", "-x509", "-newkey", "rsa:4096", "-keyout", dst_key, "-out", dst_cert, "-days", expiry, "-subj", subj]
		type = "exec"
		super().__init__(name, data, filename=None, redis_host=redis_host, type=type, copy_cache=copy_cache)
