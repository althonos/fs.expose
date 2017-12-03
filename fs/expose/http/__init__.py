# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import threading

from .server import PyfilesystemServerHandler, PyfilesystemThreadingServer


def serve(filesystem, host='127.0.0.1', port=8000):

        # create a handler for the given filesystem
        handler = PyfilesystemServerHandler(filesystem)

        # Port 0 means to select an arbitrary unused port
        server = PyfilesystemThreadingServer((host, port), handler)

        print('Serving Filesystem: {!r}'.format(filesystem))
        print('Started Server at http://{}:{}'.format(host, port))

        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = False
        server_thread.start()

        return server_thread
