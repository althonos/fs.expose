"""
fs.expose.xmlrpc
================

Server to expose an FS via XML-RPC

This module provides the necessary infrastructure to expose an FS object
over XML-RPC.  The main class is 'RPCFSServer', a SimpleXMLRPCServer subclass
designed to expose an underlying FS.

If you need to use a more powerful server than SimpleXMLRPCServer, you can
use the RPCFSInterface class to provide an XML-RPC-compatible wrapper around
an FS object, which can then be exposed using whatever server you choose
(e.g. Twisted's XML-RPC server).

"""
from __future__ import absolute_import
from __future__ import unicode_literals


import six
from six import PY3

from six.moves.xmlrpc_server import SimpleXMLRPCServer
import six.moves.xmlrpc_client as xmlrpclib
import six.moves.cPickle as pickle

from datetime import datetime
import base64

from ... import errors
from ...path import normpath
from ...opener import open_fs

class RPCFSInterface(object):
    """Wrapper to expose an FS via a XML-RPC compatible interface.

    The only real trick is using xmlrpclib.Binary objects to transport
    the contents of files.
    """

    # info keys are restricted to a subset known to work over xmlrpc
    # This fixes an issue with transporting Longs on Py3
    _allowed_methods = [
                        "listdir",
                        "isdir",
                        "isfile",
                        "exists",
                        "getinfo",
                        "setbytes",
                        "makedir",
                        "makedirs",
                        "remove",
                        "create",
                        "touch",
                        "validatepath",
                        "islink",
                        "removetree",
                        "removedir",
                        "getbytes",
                        "getsize",
                        "isempty",
                        "move",
                        "movedir",
                        "scandir",
                        "settimes",
                        "settext",
                        "setinfo",
                        "match",
                        "gettext",
                        "copy",
                        "copydir",
                        "desc",
                        "appendbytes",
                        "appendtext",
                        "getmeta",
                        "gettype",
                        "getsyspath",
                        "hassyspath",
                        "geturl",
                        "hasurl",
                        "getdetails",
                        ]


    def __init__(self, fs):
        super(RPCFSInterface, self).__init__()
        self.fs = fs

    def _dispatch(self, method, params):


        if not method in self._allowed_methods:
            # ~ print('Server',method,params,'-->','Unsupported')
            raise errors.Unsupported
        
        
        # ~ return func(*params)

        try: 
            func = getattr(self.fs, method)
            params = list(params)

            if six.PY2:
                if method in ['match']:
                    params[1] = params[1].decode('utf-8')
                else:
                    params[0] = params[0].decode('utf-8')
                

                if method in ['appendtext','settext']:
                    #Ugly Hack to let the Tests run through
                    try:
                        params[1] = params[1].decode('utf-8')
                    except:
                        pass
                
                if method in ['copy','move','copydir','movedir']:
                    params[1] = params[1].decode('utf-8')

                
            if method in ['setbytes','appendbytes']:
                try:
                    params[1] = params[1].data
                except:
                    # ~ print('Server',method,params,'-->','TypeError: Need an xmlrpc.Binary object')
                    raise TypeError('Need an xmlrpc.Binary object')
                    
            if method in ['settimes']:
                if isinstance(params[1], xmlrpclib.DateTime):
                    params[1] = datetime.strptime(params[1].value, "%Y%m%dT%H:%M:%S")
                if len(params) > 2:
                    if isinstance(params[2], xmlrpclib.DateTime):
                        params[2] = datetime.strptime(params[2].value, "%Y%m%dT%H:%M:%S")
                
            returndata = func(*params)

            if method in ['makedir',"makedirs"]:
                returndata = True
            
            if method in ['getinfo','getdetails']:
                returndata = returndata.raw
                
            if method in ['getbytes']:
                returndata = xmlrpclib.Binary(returndata)
                
            if method in ['getmeta']:
                if 'invalid_path_chars' in returndata:
                    returndata['invalid_path_chars'] = xmlrpclib.Binary(returndata['invalid_path_chars'].encode('utf-8'))
            # ~ try:
                # ~ print('Server',method,params,'-->',returndata)
            # ~ except:
                # ~ pass
            return returndata
        except:
            # ~ import traceback
            # ~ print('############## Traceback from Server ####################')
            # ~ print('Server',method,params,'-->','Error')
            # ~ traceback.print_exc()
            # ~ print('############## Traceback from Server ####################')
            raise


class RPCFSServer(SimpleXMLRPCServer):
    """Server to expose an FS object via XML-RPC.

    This class takes as its first argument an FS instance, and as its second
    argument a (hostname,port) tuple on which to listen for XML-RPC requests.
    Example::

        fs = OSFS('/var/srv/myfiles')
        s = RPCFSServer(fs,("",8080))
        s.serve_forever()

    To cleanly shut down the server after calling serve_forever, set the
    attribute "serve_more_requests" to False.
    """
    
    def __init__(self, fs, addr, requestHandler=None, logRequests=True):
        kwds = dict(allow_none=True)
        if requestHandler is not None:
            kwds['requestHandler'] = requestHandler
        if logRequests is not None:
            kwds['logRequests'] = logRequests
        self.serve_more_requests = True
        SimpleXMLRPCServer.__init__(self, addr, **kwds)
        self.register_instance(RPCFSInterface(fs))


    def serve(self):
        """Override serve_forever to allow graceful shutdown."""
        while self.serve_more_requests:
            self.handle_request()

