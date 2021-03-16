import socketserver, threading

class ReloadServerHandler(socketserver.BaseRequestHandler):

	def handle(self) :
		data = self.request.recv(512)
		if not data :
			return
		with self.server.lock :
			ret = self.server.autoconf.reload()
		if ret :
			self.request.sendall("ok")
		else :
			self.request.sendall("ko")

def run_reload_server(autoconf, lock) :
	server = socketserver.UnixStreamServer("/tmp/autoconf.pid", ReloadServerHandler)
	server.autoconf = autoconf
	server.lock = lock
	thread = threading.Thread(target=server.serve_forever)
	thread.daemon = True
	thread.start()
	return (server, thread)
