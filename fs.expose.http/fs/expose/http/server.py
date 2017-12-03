#!/usr/bin/env python3

"""Simple HTTP Server With Upload.

This module builds on BaseHTTPServer by implementing the standard GET
and HEAD requests in a fairly straightforward manner.

see: https://gist.github.com/UniIsland/3346170

Modified by merlink for integration in pyfilesystem2

see:

https://github.com/PyFilesystem/pyfilesystem2


"""

__version__ = "0.1.0"
__all__ = ["PyfsFileServerHandler"]
__author__ = "merlink"
__home_page__ = "https://github.com/PyFilesystem/pyfilesystem2"

import cgi
import mimetypes
import os
import re
import shutil
import threading

import six

from ... import errors
from ...path import combine, forcedir, normpath, splitext
from ...opener import open_fs

from six.moves.socketserver import ThreadingMixIn
from six.moves.BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from six.moves.urllib_parse import quote, unquote


class PyfilesystemServerHandler(BaseHTTPRequestHandler, object):
    """Simple HTTP request handler with GET/HEAD/POST commands.

    This serves files from the current directory and any of its
    subdirectories. The MIME type for files is determined by
    calling the .guess_type() method. And can reveive file uploaded
    by client.

    The GET/HEAD/POST requests are identical except that the HEAD
    request omits the actual contents of the file.

    """

    server_version = "PyfilesystemServerHandler/{}".format(__version__)

    def __init__(self, filesystem):
        self.fs = open_fs(filesystem)

    def __call__(self, *args, **kwargs):
        super(PyfilesystemServerHandler, self).__init__(*args, **kwargs)

    def do_GET(self):
        """Serve a GET request."""
        f = self.send_head()
        if f:
            self.copyfile(f, self.wfile)
            f.close()

    def do_HEAD(self):
        """Serve a HEAD request."""
        f = self.send_head()
        if f:
            f.close()

    def do_POST(self):
        """Serve a POST request."""
        r, info = self.deal_post_data()
        print((r, info, "by: ", self.client_address))
        f = six.BytesIO()
        f.write(b'<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write(b"<html>\n<title>Upload Result Page</title>\n")
        f.write(b"<body>\n<h2>Upload Result Page</h2>\n")
        f.write(b"<hr>\n")
        if r:
            f.write(b"<strong>Success:</strong>")
        else:
            f.write(b"<strong>Failed:</strong>")
        f.write(info.encode())
        f.write(("<br><a href=\"%s\">back</a>" % self.headers['referer']).encode())
        f.write(b"<hr><small>Powerd By: %s, check new version at "%__author__.encode())
        f.write(b"<a href=\"%s\">"%__home_page__.encode())
        f.write(b"here</a>.</small></body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        if f:
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
        fn = re.findall(r'Content-Disposition.*name="file"; filename="(.*)"', line.decode())
        if not fn:
            return (False, "Can't find out file name...")
        path = self.translate_path(self.path)
        fn = combine(path, fn[0])
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
        remainbytes -= len(preline)
        while remainbytes > 0:
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
        """Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

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
        """Helper to produce a directory listing (absent index.html).

        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().

        """

        try:
            contents = self.fs.listdir(path)
        except errors.DirectoryExpected:
            self.send_error(404, "No permission to list directory")
            return None
        contents.sort(key=lambda a: a.lower())
        f = six.BytesIO()
        displaypath = cgi.escape(unquote(self.path))
        f.write(b'<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write(b'<head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/></head>')
        f.write(("<html>\n<title>Directory listing for %s</title>\n" % displaypath).encode())
        f.write(("<body>\n<h2>Directory listing for %s</h2>\n" % displaypath).encode())
        f.write(b"<hr>\n")
        f.write(b"<form ENCTYPE=\"multipart/form-data\" method=\"post\">")
        f.write(b"<input name=\"file\" type=\"file\"/>")
        f.write(b"<input type=\"submit\" value=\"upload\"/></form>\n")
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
            f.write(('<li><a href="%s">%s</a>\n'
                    % (quote(linkname), cgi.escape(displayname))).encode())
        f.write(b"</ul>\n<hr>\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return f

    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)

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

        The SOURCE argument is a file object open for reading
        (or anything with a read() method) and the DESTINATION
        argument is a file object open for writing (or
        anything with a write() method).

        The only reason for overriding this would be to change
        the block size or perhaps to replace newlines by CRLF
        -- note however that this the default server uses this
        to copy binary data as well.

        """
        shutil.copyfileobj(source, outputfile)

    def guess_type(self, path):
        """Guess the type of a file.

        Argument is a PATH (a filename).

        Return value is a string of the form type/subtype,
        usable for a MIME Content-type header.

        The default implementation looks the file's extension
        up in the table self.extensions_map, using application/octet-stream
        as a default; however it would be permissible (if
        slow) to look inside the data to make a better guess.

        """

        base, ext = splitext(path)
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        ext = ext.lower()
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        else:
            return self.extensions_map['']

    if not mimetypes.inited:
        mimetypes.init() # try to read system mime.types
    extensions_map = mimetypes.types_map.copy()


class PyfilesystemThreadingServer(ThreadingMixIn, HTTPServer):
    pass



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
