#!/usr/bin/python3


class ReverseProxied(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        """
        If the app is behind a reverse proxy, it will modify the
        environ object to make it look like the request was received on the app directly

        :param environ: The WSGI environment dict
        :param start_response: This is the WSGI-compatible start_response function that the
        :return: A WSGI application.
        """
        script_name = environ.get("HTTP_X_SCRIPT_NAME", "")
        if script_name:
            environ["SCRIPT_NAME"] = script_name
            path_info = environ["PATH_INFO"]
            if path_info.startswith(script_name):
                environ["PATH_INFO"] = path_info[len(script_name) :]

        scheme = environ.get("HTTP_X_FORWARDED_PROTO", "")
        if scheme:
            environ["wsgi.url_scheme"] = scheme
        return self.app(environ, start_response)
