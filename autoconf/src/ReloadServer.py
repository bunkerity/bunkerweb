import socketserver, threading, utils, os, stat

class ReloadServerHandler(socketserver.StreamRequestHandler):

	def handle(self) :
		locked = False
		try :
			# Get lock order from client
			data = self.request.recv(512)
			if not data or data != b"lock" :
				return
			self.server.controller.lock.acquire()
			locked = True

			# Get reload order from client
			data = self.request.recv(512)
			if not data or data != b"reload" :
				self.server.controller.lock.release()
				return
			if self.server.controller.reload() :
				self.request.sendall(b"ok")
			else :
				self.request.sendall(b"ko")

			# Release the lock
			self.server.controller.lock.release()

		except Exception as e :
			utils.log("Exception ReloadServer : " + str(e))
			if locked :
				self.server.controller.lock.release()

def run_reload_server(controller) :
	server = socketserver.UnixStreamServer("/tmp/autoconf.sock", ReloadServerHandler)
	os.chown("/tmp/autoconf.sock", 0, 101)
	os.chmod("/tmp/autoconf.sock", 0o770)
	server.controller = controller
	thread = threading.Thread(target=server.serve_forever)
	thread.daemon = True
	thread.start()
	return (server, thread)
