from Job import Job

import datetime, gzip, shutil, os

class GeoIP(Job) :

	def __init__(self, redis_host=None, copy_cache=False) :
		name = "geoip"
		data = ["https://download.db-ip.com/free/dbip-country-lite-" + datetime.datetime.today().strftime("%Y-%m") + ".mmdb.gz"]
		filename = "geoip.mmdb.gz"
		type = "file"
		super().__init__(name, data, filename, redis_host=redis_host, type=type, copy_cache=copy_cache)

	def run(self) :
		super().run()
		count = 0
		with gzip.open("/etc/nginx/geoip.mmdb.gz", "rb") as f :
			with open("/tmp/geoip.mmdb", "wb") as f2 :
				while True :
					chunk = f.read(8192)
					if not chunk :
						break
					f2.write(chunk)
					count += 1
		shutil.copyfile("/tmp/geoip.mmdb", "/etc/nginx/geoip.mmdb")
		os.remove("/tmp/geoip.mmdb")
		os.remove("/etc/nginx/geoip.mmdb.gz")
