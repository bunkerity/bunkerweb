import docker, subprocess, os, stat, sys

if __name__ == "__main__" :

	# Linux or single Docker use case
	if os.path.isfile("/usr/sbin/nginx") :
		proc = subprocess.run(["/usr/sbin/nginx", "-s", "reload"], capture_output=True)
		if proc.returncode != 0 :
			print("[!] can't reload nginx (status code = " + str(proc.returncode) + ")"
			if len(proc.stdout.decode("ascii")) > 1 :
				print(proc.stdout.decode("ascii"))
			if len(proc.stderr.decode("ascii")) > 1 :
				print(proc.stderr.decode("ascii"))
			sys.exit(1)

	# Autoconf case (Docker, Swarm and Ingress)
	mode = os.stat("/tmp/autoconf.sock")
	elif stat.S_ISSOCK(mode) :
		client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		client.connect("/tmp/autoconf.sock")
		client.send("reload".encode("utf-8"))
		data = client.recv(512)
		client.close()
        if not data or data.decode("utf-8") != "ok" :
                sys.exit(2)

	sys.exit(0)
