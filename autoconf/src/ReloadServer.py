import socketserver, threading, os, stat

from logger import log

class ReloadServerHandler(socketserver.BaseRequestHandler):

	def handle(self) :
		locked = False
		try :

			while True :
				data = self.request.recv(512)
				print(data, flush=True)
				if not data or not data in [b"lock", b"reload", b"unlock", b"acme"] :
					break
				if data == b"lock" :
					self.server.controller.lock.acquire()
					locked = True
					self.request.sendall(b"ok")
				elif data == b"unlock" :
					self.server.controller.lock.release()
					locked = False
					self.request.sendall(b"ok")
				elif data == b"acme" :
					ret = self.server.controller.send()
					if ret :
						self.request.sendall(b"ok")
					else :
						self.request.sendall(b"ko")
				elif data == b"reload" :
					ret = self.server.controller.reload()
					if ret :
						self.request.sendall(b"ok")
					else :
						self.request.sendall(b"ko")
		except Exception as e :
			log("RELOADSERVER", "ERROR", "exception : " + str(e))
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
