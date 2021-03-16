#!/usr/bin/python3

import sys, socket, os

if not os.path.exists("/tmp/autoconf.sock") :
	sys.exit(1)

try :
	client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	client.connect("/tmp/autoconf.sock")
	client.send("reload".encode("utf-8"))
	data = client.recv(512)
	client.close()
	if not data or data.decode("utf-8") != "ok" :
		sys.exit(3)
except Exception as e :
	sys.exit(2)

sys.exit(0)
