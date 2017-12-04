# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import threading

from .xmlrpc import RPCFSServer
# ~ from six.moves.xmlrpc_server import SimpleXMLRPCRequestHandler

def serve(filesystem, host='127.0.0.1', port=8000, debug=True):
        xmlrpcserver = RPCFSServer(filesystem,(host,port))

        server_thread = threading.Thread(target=xmlrpcserver.serve_forever)
        server_thread.daemon = False
        server_thread.shutdown = xmlrpcserver.shutdown
        server_thread.start()

        return server_thread
