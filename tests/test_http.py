# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import textwrap
import threading
import unittest

import fs
import six
import tenacity

from contextlib import closing

from fs.expose.http import PyfilesystemServerHandler, serve
from fs.errors import PermissionDenied
from six.moves.urllib.request import urlopen, Request
from six.moves.urllib.error import HTTPError
from six.moves.urllib.parse import quote

from .utils import mock


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

    retry = tenacity.retry(
        stop=tenacity.stop_after_attempt(4),
        wait=tenacity.wait_fixed(1),
        reraise=True,
    )

    @classmethod
    def _url(cls, resource):
        safe_resource = quote(resource.encode('utf-8'))
        return "http://{}:{}/{}".format(cls.host, cls.port, safe_resource)

    @classmethod
    def setUpClass(cls):
        cls.test_fs = fs.open_fs('mem://')
        cls.server_thread = serve(cls.test_fs, cls.host, cls.port)

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
        cls.server_thread.join()
        cls.test_fs.close()

    @retry
    def test_get_file(self):
        with closing(urlopen(self._url('root.txt'))) as res:
            self.assertEqual(res.read(), b'Hello, World!')
        with closing(urlopen(self._url('top/file.bin'))) as res:
            self.assertEqual(res.read(), b'Hi there!')

    @retry
    def test_get_file_unicode(self):
        with closing(urlopen(self._url('top/middle/bottom/☻.txt'))) as res:
            self.assertEqual(res.read(), b'Happy face !')

    @retry
    def test_get_file_not_found(self):
        with self.assertRaises(HTTPError) as err:
            urlopen(self._url('not-found.txt'))
        self.assertEqual(err.exception.code, 404)

    @retry
    def test_list_directory(self):
        with closing(urlopen(self._url('top'))) as res:
            text = res.read()
            self.assertIn(b'<h2>Directory listing for /top/</h2>', text)
            self.assertIn(b'<a href="file.bin">file.bin</a>', text)
            self.assertIn(b'<a href="middle/">middle/</a>', text)

        self.test_fs.remove('top/file.bin')

        with closing(urlopen(self._url('top'))) as res:
            text = res.read()
            self.assertNotIn(b'<a href="file.bin">file.bin</a>', text)
            self.assertIn(b'<a href="middle/">middle/</a>', text)

        with mock.patch.object(self.test_fs, 'islink', new=lambda _: True):
            with closing(urlopen(self._url('top'))) as res:
                text = res.read()
                self.assertIn(b'<a href="middle/">middle@</a>', text)

    @retry
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
        request.add_header("Content-Type", "multipart/form-data; boundary=-DATA")
        request.add_header("Referer", 'top/middle/')

        with closing(urlopen(request)) as res:
            self.assertEqual(res.code, 200)

        self.assertTrue(self.test_fs.exists('top/middle/upload.txt'))
        self.assertEqual(self.test_fs.gettext('top/middle/upload.txt'), 'This is an upload test.\n')

    @retry
    def test_head_request(self):
        request = Request(self._url('root.txt'))
        request.get_method = lambda : 'HEAD'
        with closing(urlopen(request)) as res:
            self.assertEqual(res.headers['Content-type'], 'text/plain')
            self.assertEqual(int(res.headers['Content-Length']), len(b'Hello, World!'))

    @retry
    def test_mime_type(self):
        request = Request(self._url('video.mp4'))
        request.get_method = lambda : 'HEAD'
        with closing(urlopen(request)) as res:
            self.assertEqual(res.headers['Content-type'], 'video/mp4')

    @retry
    def test_permission_denied(self):
        with mock.patch.object(self.test_fs, 'listdir', mock.MagicMock()) as mock_method:
            mock_method.side_effect = PermissionDenied
            with self.assertRaises(HTTPError) as err:
                urlopen(self._url('/'))
            self.assertEqual(err.exception.code, 403)

    @retry
    def test_upload_no_boundary(self):
        with self.assertRaises(HTTPError) as handler:
            data = b""
            request = Request(self._url('top/middle/'), data=data)
            request.add_header("Content-Length", len(data))
            request.add_header("Content-Type", "multipart/form-data")
            request.get_method = lambda: "POST"
            urlopen(request)
        self.assertEqual(handler.exception.code, 400)
        self.assertEqual(
            handler.exception.reason,
            "'Content-Type' header does not contain a boundary"
        )

    @retry
    def test_upload_wrong_data(self):
        with self.assertRaises(HTTPError) as handler:
            data = b"\n"
            request = Request(self._url('top/middle/'), data=data)
            request.add_header("Content-Type", "multipart/form-data; boundary=-DATA")
            request.add_header("Referer", 'top/middle/')
            urlopen(request)
        self.assertEqual(handler.exception.code, 400)
        self.assertEqual(
            "content does not begin with boundary",
            handler.exception.reason,
        )

    @retry
    def test_upload_no_filename(self):
        with self.assertRaises(HTTPError) as handler:
            data = b"--DATA\n"
            request = Request(self._url('top/middle/'), data=data)
            request.add_header("Content-Type", "multipart/form-data; boundary=-DATA")
            request.add_header("Referer", 'top/middle/')
            urlopen(request)
        self.assertEqual(handler.exception.code, 400)
        self.assertEqual(
            "cannot find filename",
            handler.exception.reason,
        )

    @retry
    def test_upload_directory(self):
        with self.assertRaises(HTTPError) as handler:
            data = textwrap.dedent("""
                -DATA
                Content-Disposition: form-data; name="file"; filename="/"
                Content-Type: text/plain
                -DATA--
                """).lstrip().encode('utf-8')
            request = Request(self._url('top/middle/'), data=data)
            request.add_header("Content-Type", "multipart/form-data; boundary=-DATA")
            request.add_header("Referer", 'top/middle/')
            urlopen(request)
        self.assertEqual(handler.exception.code, 403)
        self.assertEqual(
            "cannot create file '/top/middle/'",
            handler.exception.reason,
        )

    @retry
    def test_upload_unexpected_end_of_data(self):
        with self.assertRaises(HTTPError) as handler:
            data = textwrap.dedent("""
                -DATA
                Content-Disposition: form-data; name="file"; filename="test.txt"
                Content-Type: text/plain

                Beginning of test text

                """).lstrip().encode('utf-8')
            request = Request(self._url('top/middle/'), data=data)
            request.add_header("Content-Type", "multipart/form-data; boundary=-DATA")
            request.add_header("Referer", 'top/middle/')
            urlopen(request)
        self.assertEqual(handler.exception.code, 400)
        self.assertEqual(
            "unexpected end of data",
            handler.exception.reason,
        )
