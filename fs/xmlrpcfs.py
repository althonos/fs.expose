# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from contextlib import closing
from xml.parsers.expat import ExpatError 

import six
from six.moves import xmlrpc_client
import six.moves.xmlrpc_client as xmlrpclib
from six.moves.xmlrpc_client import Fault
from fs.errors import *
from fs import errors, info

class XMLRPC_FS(object):
    def __init__(self, *args,**kwargs):
        self.proxy = xmlrpc_client.ServerProxy(*args,**kwargs)

    def __getattr__(self, name):
        # magic method dispatcher
        return xmlrpclib._Method(self.__request, name)

    def __call__(self, attr):
        """A workaround to get special attributes on the ServerProxy
           without interfering with the magic __getattr__
        """
        if attr == "close":
            return self.__close
        elif attr == "transport":
            return self.__transport
        raise AttributeError("Attribute %r not found" % (attr,))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.__close()



    def __request(self, methodname, params):
        
        #Presendfunctions
        if methodname in ['getmeta']:
            if len(params) == 0:
                params = ('',)
                
        if methodname in ['settext','appendtext']:
            if type(params[1]) == bytes:
                raise TypeError('Bytes not allowed')

        if six.PY2:
            if methodname in ['setbytes','appendbytes']:

                if type(params[1]) == unicode:
                    raise TypeError('Unicode not allowed')
        
        if methodname in ['setbytes','appendbytes']:
            params = (params[0],xmlrpclib.Binary(params[1]))

        #Send
        func = getattr(self.proxy, methodname)
        
        try:
            data = func(*params)
            # ~ try:
                # ~ print(methodname, params,'-->',data)
            # ~ except:
                # ~ pass
                
        except ExpatError as err:
              raise errors.InvalidCharsInPath(err)
              
        except Fault as err:
            err = str(err)
            if 'fs.errors' in err:
                x = err.split('fs.errors.')[1].split("'")[0]
                errorobj = getattr(errors, x)
                raise errorobj(err,'')
            elif 'exceptions.TypeError' in err:
                raise TypeError(err)
            elif 'ExpatError' in err:
                raise errors.InvalidCharsInPath(err)
            else:
                # ~ print(err)
                raise


        #Postsendfunctions
        if methodname in ['getbytes']:
            data = data.data
            
        if methodname in ['getmeta']:
            if 'invalid_path_chars' in data:
                data['invalid_path_chars'] = data['invalid_path_chars'].data.decode('utf-8')
            
        if six.PY2:
            if methodname in ['getinfo','getdetails']:
                data['basic']['name'] = data['basic']['name'].decode('utf-8')
            if methodname in ['listdir']:
                outlist = []
                for entry in data:
                    outlist.append(entry.decode('utf-8'))
                data = outlist
            
            if methodname in ['gettext']:
                #Ugly Hack to let the Tests run through
                try:
                    data = data.decode('utf-8')
                except:
                    pass
        if methodname in ['getinfo','getdetails']:
            data = info.Info(data)
                
        return data