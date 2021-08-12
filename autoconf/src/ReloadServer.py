import socketserver, threading, os, stat

from logger import log

class ReloadServerHandler(socketserver.StreamRequestHandler):

	def handle(self) :
		locked = False
		try :

			while True :
				data = self.request.recv(512)
				if not data or not data in [b"lock", b"reload", b"unlock"] :
					break
				if data == b"lock" :
					log("RELOADSERVER", "ERROR", "lock")
					self.server.controller.lock.acquire()
					locked = True
					self.request.sendall(b"ok")
				elif data == b"unlock" :
					log("RELOADSERVER", "ERROR", "unlock")
					self.server.controller.lock.release()
					locked = False
					self.request.sendall(b"ok")
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
