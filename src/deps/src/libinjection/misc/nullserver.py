#!/usr/bin/env python

# A 'nullserver' that accepts input and generates output
# to trick sqlmap into thinking it's a database-driven site
#

import sys
import logging
import urllib

import tornado.httpserver
import tornado.ioloop
import tornado.web
import libinjection

class ShutdownHandler(tornado.web.RequestHandler):
    def get(self):
        global fd
        fd.close()
        sys.exit(0)


class CountHandler(tornado.web.RequestHandler):
    def get(self):
        global count
        self.write(str(count) + "\n")

def boring(arg):
    if arg == '':
        return True

    if arg == 'foo':
        return True

    if arg == 'NULL':
        return True

    try:
        float(arg)
        return True
    except ValueError:
        pass

    return False;

class NullHandler(tornado.web.RequestHandler):

    def get(self):
        global fd
        global count
        params = self.request.arguments.get('id', [])
        sqli = False

        if len(params) == 0 or (len(params) == 1 and boring(params[0])):
            # if no args, or a single value with uninteresting input
            # then just exit
            self.write("<html><head><title>safe</title></head><body></body></html>")
            return

        for arg in params:
            sqli = libinjection.detectsqli(arg)
            if sqli:
                break

        # we didn't detect it :-(
        if not sqli:
            count += 1
            args = [ arg.strip() for arg in params ]
            #fd.write(' | '.join(args) + "\n")
            for arg in args:
                extra = {}
                sqli = libinjection.detectsqli(arg, extra)
                logging.error("\t" + arg + "\t" + str(sqli) + "\t" + extra['fingerprint'] + "\n")
            #for arg in param:
            #    fd.write(arg + "\n")
            #    #fd.write(urllib.quote_plus(arg) + "\n")
            self.set_status(500)
            self.write("<html><head><title>safe</title></head><body></body></html>")
        else:
            self.write("<html><head><title>sqli</title></head><body></body></html>")

import os
settings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
    "cookie_secret": "yo mama sayz=",
    "xsrf_cookies": True,
    "gzip": False
}

application = tornado.web.Application([
    (r"/null", NullHandler),
    (r"/shutdown", ShutdownHandler),
    (r"/count", CountHandler)
    ], **settings)


if __name__ == "__main__":
    global fd
    global count

    count = 0

    fd = open('./sqlmap-false-negatives.txt', 'w')

    import tornado.options
    #tornado.options.parse_config_file("/etc/server.conf")
    tornado.options.parse_command_line()

    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
