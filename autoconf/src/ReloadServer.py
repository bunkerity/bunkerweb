import socketserver, threading, utils, os, stat

class ReloadServerHandler(socketserver.StreamRequestHandler):

	def handle(self) :
		try :
			data = self.request.recv(512)
			if not data :
				return
			with self.server.lock :
				ret = self.server.autoconf.reload()
			if ret :
				self.request.sendall("ok".encode("utf-8"))
			else :
				self.request.sendall("ko".encode("utf-8"))
		except Exception as e :
			utils.log("Exception " + str(e))

def run_reload_server(autoconf, lock) :
	server = socketserver.UnixStreamServer("/tmp/autoconf.sock", ReloadServerHandler)
	os.chown("/tmp/autoconf.sock", 0, 101)
	os.chmod("/tmp/autoconf.sock", 0o770)
	server.autoconf = autoconf
	server.lock = lock
	thread = threading.Thread(target=server.serve_forever)
	thread.daemon = True
	thread.start()
	return (server, thread)
