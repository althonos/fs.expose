# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import textwrap
import threading
import unittest

import six
import fs

from fs.expose.http import PyfilesystemThreadingServer, PyfilesystemServerHandler
from six.moves.urllib.request import urlopen, Request
from six.moves.urllib.error import HTTPError


class TestGuessType(unittest.TestCase):

    @staticmethod
    def mimetype(filename):
        return PyfilesystemServerHandler.guess_type(filename)

    def test_known_extension(self):
        self.assertEqual(self.mimetype('video.mp4'), 'video/mp4')
        self.assertEqual(self.mimetype('page.html'), 'text/html')

    def test_known_extension_upper(self):
        self.assertEqual(self.mimetype('VIDEO.MP4'), 'video/mp4')
        self.assertEqual(self.mimetype('PAGE.HTML'), 'text/html')

    def test_unknown_extension(self):
        self.assertEqual(self.mimetype('FILE.BULLSHIT'), 'application/octet-stream')



class TestExposeHTTP(unittest.TestCase):

    host = 'localhost'
    port = 8080

    @classmethod
    def _url(cls, resource):
        return "http://{}:{}/{}".format(cls.host, cls.port, resource)

    @classmethod
    def setUpClass(cls):
        cls.test_fs = fs.open_fs('mem://')
        handler = PyfilesystemServerHandler(cls.test_fs)
        adress = (cls.host, cls.port)
        cls.server = PyfilesystemThreadingServer(adress, handler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = False
        cls.server_thread.start()

    def setUp(self):
        self.test_fs.makedirs('top/middle/bottom')
        self.test_fs.settext('root.txt', 'Hello, World!')
        self.test_fs.setbytes('video.mp4', b'\x00\x00\x00 ftypisom\x00\x00\x02\x00')
        self.test_fs.setbytes('top/file.bin', b'Hi there!')

    def tearDown(self):
        self.test_fs.removetree('/')

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server_thread.join()
        cls.test_fs.close()

    def test_get_file(self):
        with urlopen(self._url('root.txt')) as res:
            self.assertEqual(res.read(), b'Hello, World!')
        with urlopen(self._url('top/file.bin')) as res:
            self.assertEqual(res.read(), b'Hi there!')

    def test_get_file_not_found(self):
        with self.assertRaises(HTTPError) as err:
            urlopen(self._url('not-found.txt'))
        self.assertEqual(err.exception.code, 404)

    def test_list_directory(self):
        with urlopen(self._url('top')) as res:
            text = res.read()
            self.assertIn(b'<h2>Directory listing for /top/</h2>', text)
            self.assertIn(b'<a href="file.bin">file.bin</a>', text)
            self.assertIn(b'<a href="middle/">middle/</a>', text)

        self.test_fs.remove('top/file.bin')

        with urlopen(self._url('top')) as res:
            text = res.read()
            self.assertNotIn(b'<a href="file.bin">file.bin</a>', text)
            self.assertIn(b'<a href="middle/">middle/</a>', text)

    def test_upload(self):

        self.assertFalse(self.test_fs.exists('top/middle/upload.txt'))

        data = textwrap.dedent("""
        -DATA
        Content-Disposition: form-data; name="file"; filename="upload.txt"
        Content-Type: text/plain

        This is an upload test.

        -DATA--
        """).lstrip().encode('utf-8')

        request = Request(self._url('top/middle/'), data=data)
        request.add_header("Content-Length", 1000)
        request.add_header("Content-Type", "multipart/form-data; boundary=-DATA")
        request.get_method = lambda: "POST"

        with urlopen(request) as res:
            self.assertEqual(res.code, 200)

        self.assertTrue(self.test_fs.exists('top/middle/upload.txt'))
        self.assertEqual(self.test_fs.gettext('top/middle/upload.txt'), 'This is an upload test.\n')

    def test_head_request(self):
        request = Request(self._url('root.txt'))
        request.get_method = lambda : 'HEAD'
        with urlopen(request) as res:
            self.assertEqual(res.getheader('Content-type'), 'text/plain')
            self.assertEqual(int(res.getheader('Content-Length')), len(b'Hello, World!'))

    def test_mime_type(self):
        request = Request(self._url('video.mp4'))
        request.get_method = lambda : 'HEAD'
        with urlopen(request) as res:
            self.assertEqual(res.getheader('Content-type'), 'video/mp4')
