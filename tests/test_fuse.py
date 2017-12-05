# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import functools
import os
import textwrap
import tempfile
import multiprocessing
import time
import unittest

import fs
import fuse
import six

from fs.test import FSTestCases
from fs.expose.fuse.operations import PyfilesystemFuseOperations


class _TestFuseMount(FSTestCases):

    _source_url = NotImplemented

    def make_fs(self):
        self.mountpoint = tempfile.mkdtemp()
        self.source_fs = fs.open_fs(self._source_url)
        self.fuse_process = multiprocessing.Process(
            target=fuse.FUSE,
            args=(PyfilesystemFuseOperations(self.source_fs), self.mountpoint),
            kwargs={"foreground": True, "debug": False},
        )
        self.fuse_process.start()
        time.sleep(0.1)
        test_fs = fs.open_fs(self.mountpoint)
        self.assertTrue(test_fs.isempty('/'))
        return test_fs

    def destroy_fs(self, fs):
        fs.close()
        self.fuse_process.terminate()
        self.source_fs.removetree('/')
        self.source_fs.close()
        self.fuse_process.join()
        os.rmdir(self.mountpoint)

    def test_mounted(self):
        with open("/etc/mtab") as f:
            self.assertIn(self.mountpoint, f.read())

# @unittest.skipIf(True, "")
class TestFuseMemFS(_TestFuseMount, unittest.TestCase):
    _source_url = "mem://"

class TestFuseMountTempFS(_TestFuseMount, unittest.TestCase):
    _source_url = "temp://"
