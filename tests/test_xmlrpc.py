# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import textwrap
import threading
import unittest
import base64

import six
import fs

from contextlib import closing

from fs.expose.xmlrpc import serve
from six.moves import xmlrpc_client
from six.moves.xmlrpc_client import Fault
from fs.errors import *


from .utils import mock


class TestExposeXMLRPC(unittest.TestCase):

    host = 'localhost'
    port = 8081

    @classmethod
    def _url(cls, resource):
        safe_resource = quote(resource.encode('utf-8'))
        return "http://{}:{}/{}".format(cls.host, cls.port, safe_resource)
    
    @classmethod
    def _encode_path(cls, path):
        return six.text_type(base64.b64encode(path.encode("utf8")),'ascii')

    @classmethod
    def setUpClass(cls):
        cls.test_fs = fs.open_fs('mem://')
        cls.server_thread = serve(cls.test_fs, cls.host, cls.port)
        cls.proxy = xmlrpc_client.ServerProxy("http://%s:%s/"%(cls.host,cls.port))#,verbose=True)
        

    def setUp(self):
        self.test_fs.makedirs('top/middle/bottom')
        self.test_fs.settext('root.txt', 'Hello, World!')
        self.test_fs.setbytes('video.mp4', b'\x00\x00\x00 ftypisom\x00\x00\x02\x00')
        self.test_fs.setbytes('top/file.bin', b'Hi there!')
        self.test_fs.setbytes('top/middle/bottom/☻.txt', b'Happy face !')

    def tearDown(self):
        self.test_fs.removetree('/')

    @classmethod
    def tearDownClass(cls):
        cls.server_thread.shutdown()
        cls.test_fs.close()

    def test_listdir(self):
        dirlist = self.proxy.listdir(u'/')
        self.assertEqual(dirlist,['top', 'root.txt', 'video.mp4'])
        dirlist = self.proxy.listdir('/top/middle/bottom/')
        self.assertEqual(dirlist[0],'☻.txt')
        
        with self.assertRaises(Fault) as err:
            self.proxy.listdir('/notexist')
        assert 'fs.errors.ResourceNotFound' in str(err.exception)
        
        with mock.patch.object(self.test_fs, 'listdir', mock.MagicMock()) as mock_method:
            mock_method.side_effect = PermissionDenied
            with self.assertRaises(Fault) as err:
                self.proxy.listdir('/')
        assert 'fs.errors.PermissionDenied' in str(err.exception)

        # ~ #Not working?
        # ~ with mock.patch.object(self.test_fs, 'listdir', mock.MagicMock()) as mock_method:
            # ~ mock_method.side_effect = DirectoryExpected
            # ~ with self.assertRaises(Fault) as err:
                # ~ self.proxy.listdir('/')
        # ~ print(str(err.exception))
        # ~ assert 'fs.errors.DirectoryExpected' in str(err.exception)

