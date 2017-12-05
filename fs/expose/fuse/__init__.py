# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import ctypes
import fuse

from .operations import PyfilesystemFuseOperations
# from .mounter import PyfilesystemFuseMounter

__all__ = ["mount", "PyfilesystemFuseOperations"]
__version__ = "0.1.0"
__author__ = "althonos"
__home_page__ = "https://github.com/althonos/fs.expose"


# def mount(filesystem, mountpoint, debug=False, foreground=False, threads=True):
#
#         args = ["", mountpoint]
#         if debug: args.append('-d')
#         if foreground: args.append('-f')
#         if not threads: args.append('-s')
#
#         args = [arg.encode('utf-8') for arg in args]
#
#         argv = ()
#
#
#
#
#         operations = PyfilesystemFuseOperations(filesystem)
#
#
#
#
#
#
#         return fuse.FUSE(operations, mountpoint, debug=debug, foreground=foreground)
