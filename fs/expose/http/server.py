# coding: utf-8
"""Simple HTTP Server With Upload.

This module builds on BaseHTTPServer by implementing the standard GET
and HEAD requests in a fairly straightforward manner.

see: https://gist.github.com/UniIsland/3346170

Modified by merlink for integration in pyfilesystem2

see:

https://github.com/PyFilesystem/pyfilesystem2

"""

__version__ = "0.1.0"
__all__ = ["PyfilesystemServerHandler", "PyfilesystemThreadingServer"]
__author__ = "merlink"
__home_page__ = "https://github.com/althonos/fs.expose"

import cgi
import mimetypes
import os
import re
import shutil

import six

from ... import errors
from ...path import combine, forcedir, normpath, splitext
from ...opener import open_fs

from six.moves.socketserver import ThreadingMixIn
from six.moves.BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from six.moves.urllib.parse import quote, unquote


class PyfilesystemServerHandler(BaseHTTPRequestHandler, object):
    """Simple HTTP request handler with GET/HEAD/POST commands.

    This serves files from the current directory and any of its
    subdirectories. The MIME type for files is determined by
    calling the `~PyfilesystemServerHandler.guess_type` method.
    And can reveive file uploaded by client.

    The GET/HEAD/POST requests are identical except that the HEAD
    request omits the actual contents of the file.

    """

    server_version = "PyfilesystemServerHandler/{}".format(__version__)
    _regex_filename = re.compile(r'Content-Disposition.*name="file"; filename="(.*)"')

    def __init__(self, filesystem):
        self.fs = open_fs(filesystem)

    def __call__(self, *args, **kwargs):
        super(PyfilesystemServerHandler, self).__init__(*args, **kwargs)

    def do_GET(self):
        """Serve a GET request.
        """
        f = self.send_head()
        if f:
            self.copyfile(f, self.wfile)
            f.close()

    def do_HEAD(self):
        """Serve a HEAD request.
        """
        f = self.send_head()
        if f:
            f.close()

    def do_POST(self):
        """Serve a POST request.
        """
        r, info = self.deal_post_data()
        print((r, info, "by: ", self.client_address))
        f = six.BytesIO()
        f.write(b'<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write(b'<head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/></head>')
        f.write(b"<html>\n<title>Upload Result Page</title>\n")
        f.write(b"<body>\n<h2>Upload Result Page</h2>\n")
        f.write(b"<hr>\n")
        if r:
            f.write(b"<strong>Success:</strong>")
        else:
            f.write(b"<strong>Failed:</strong>")
        f.write(info.encode('utf-8'))
        if 'referer' in self.headers:
            f.write('<br><a href="%s">back</a>'.format(self.headers['referer']).encode('utf-8'))
        f.write("<hr><small>Powered by: {}, check new version at ".format(__author__).encode('utf-8'))
        f.write('<a href="%s">'.format(__home_page__).encode('utf-8'))
        f.write(b"here</a>.</small></body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        self.copyfile(f, self.wfile)
        f.close()

    def deal_post_data(self):
        content_type = self.headers['content-type']
        if not content_type:
            return (False, "Content-Type header doesn't contain boundary")
        boundary = content_type.split("=")[1].encode()
        remainbytes = int(self.headers['content-length'])
        line = self.rfile.readline()
        remainbytes -= len(line)
        if not boundary in line:
            return (False, "Content NOT begin with boundary")
        line = self.rfile.readline()
        remainbytes -= len(line)
        fn = self._regex_filename.search(line.decode()).group(1)
        if not fn:
            return (False, "Can't find out file name...")
        path = self.translate_path(self.path)
        fn = combine(path, fn)
        line = self.rfile.readline()
        remainbytes -= len(line)
        line = self.rfile.readline()
        remainbytes -= len(line)

        if fn == '/':
            return (False, "Can't create file with name /")

        try:
            out = self.fs.open(fn, 'wb')
        except errors.FileExpected:
            return (False, "Can't create file to write, do you have permission to write?")

        preline = self.rfile.readline()
        print(preline)
        remainbytes -= len(preline)
        while remainbytes > 0:
            print(line)
            line = self.rfile.readline()
            remainbytes -= len(line)
            if boundary in line:
                preline = preline[0:-1]
                if preline.endswith(b'\r'):
                    preline = preline[0:-1]
                out.write(preline)
                out.close()
                return (True, "File '%s' upload success!" % fn)
            else:
                out.write(preline)
                preline = line
        return (False, "Unexpect Ends of data.")

    def send_head(self):
        """Send the response code and MIME headers.

        This code is common to both GET and HEAD commands.

        Returns:
            None: when an error occured.
            six.BytesIO: a file object which has to be copied to the output
                         file by the caller and must always be closed.

        """
        path = self.translate_path(self.path)
        f = None
        if self.fs.isdir(path):
            if not self.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return None

            #Serves Folders with index files directly without listing them
            #could bevome an opional parametet
            # ~ for index in "index.html", "index.htm":
                # ~ index = combine(path, index)
                # ~ if self.fs.exists(index):
                    # ~ path = index
                    # ~ break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = self.fs.open(path, 'rb')
        except errors.ResourceNotFound:
            self.send_error(404, "File not found")
            return None
        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Content-Length", self.fs.getsize(path))
        #todof
        # ~ self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

    def list_directory(self, path):
        """Produce a directory listing.

        The headers are always sent, making the interface the same as for
        `~PyfilesystemServerHandler.send_head`.

        Arguments:
            path (str): the path to a filesystem resource.

        Returns:
            six.BytesIO: an HTML page listing the directory contents.
            None: when an error occured while trying to list the directory.

        """
        try:
            contents = self.fs.listdir(path)
        except errors.PermissionDenied:
            self.send_error(403, "No permission to list directory")
            return None
        contents.sort(key=lambda a: a.lower())
        f = six.BytesIO()
        displaypath = cgi.escape(unquote(self.path))
        f.write(b'<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write(b'<head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/></head>')
        f.write("<html>\n<title>Directory listing for {}</title>\n".format(
            displaypath).encode('utf-8'))
        f.write("<body>\n<h2>Directory listing for {}</h2>\n".format(
            displaypath).encode('utf-8'))
        f.write(b"<hr>\n")
        f.write(b'<form ENCTYPE="multipart/form-data" method="post">')
        f.write(b'<input name="file" type="file"/>')
        f.write(b'<input type="submit" value="upload"/></form>\n')
        f.write(b"<hr>\n<ul>\n")
        for name in contents:
            fullname = combine(path, name)
            displayname = linkname = name
            # Append / for directories or @ for symbolic links
            if self.fs.isdir(fullname):
                displayname = linkname = forcedir(name)
            if self.fs.islink(fullname):
                displayname = name + "@"
                # Note: a link to a directory displays with @ and links with /
            f.write('<li><a href="{}">{}</a>\n'.format(
                quote(linkname), cgi.escape(displayname)).encode('utf-8'))
        f.write(b"</ul>\n<hr>\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return f

    def translate_path(self, path):
        """Translate a path to the local filename syntax.

        Arguments:
            path (str): a slash separated path.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.

        Todo:
            * Diagnose special components
        """
        # abandon query parameters
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        path = normpath(unquote(path))
        # ~ words = path.split('/')
        # ~ words = [_f for _f in words if _f]
        # ~ path = os.getcwd()
        # ~ for word in words:
            # ~ drive, word = os.path.splitdrive(word)
            # ~ head, word = os.path.split(word)
            # ~ if word in (os.curdir, os.pardir): continue
            # ~ path = os.path.join(path, word)

        if six.PY2:
            path = path.decode('utf-8')

        return path

    def copyfile(self, source, outputfile):
        """Copy all data between two file objects.

        Arguments:
            source (io.IOBase): a file object open for reading.
            dest (io.IOBase): a file object open for writing.

        The only reason for overriding this would be to change the block
        size or perhaps to replace newlines by CRLF -- note however that
        the default server uses this method to copy binary data as well.
        """
        shutil.copyfileobj(source, outputfile)

    @staticmethod
    def guess_type(path):
        """Guess the type of a file.

        The default implementation looks the file's extension up in the
        `~PyfilesystemServerHandler.extensions_map`, using
        ``application/octet-stream`` as a default; however it would be
        permissible (if slow) to look inside the data to make a better guess.

        Arguments:
            path (str): a filename.

        Returns:
            str: a MIME type (of the form type/subtype).

        """
        mimetype, encoding = mimetypes.guess_type(path)
        return mimetype or 'application/octet-stream'

    if not mimetypes.inited:    # pragma: no cover
        mimetypes.init()


class PyfilesystemThreadingServer(ThreadingMixIn, HTTPServer):
    pass
