# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
import errno
import functools
import os
import posix
import textwrap
import tempfile
import multiprocessing
import stat
import time
import unittest

import fs
import fuse
import six

from fs.info import Info
from fs.test import FSTestCases
from fs.wrap import read_only
from fs.enums import ResourceType
from fs.expose.fuse.operations import PyfilesystemFuseOperations
from fs.expose.fuse.utils import timestamp

from .utils import mock


class _TestFuseMount(FSTestCases):

    _source_url = NotImplemented

    @staticmethod
    def _is_mounted(mountpoint):
        with open('/etc/mtab') as f:
            for line in f:
                if mountpoint == line.split(" ")[1]:
                    return True
        return False

    def _mount(self, timeout=1, sleeptime=0.001):
        self.fuse_process.start()
        while not self._is_mounted(self.mountpoint) and timeout:
            timeout -= sleeptime
            time.sleep(sleeptime)
        if not timeout:
            self.fail('could not mount {} to {}'.format(
                self.source_fs, self.mountpoint))

    def make_fs(self):
        self.mountpoint = tempfile.mkdtemp()
        self.source_fs = fs.open_fs(self._source_url)
        self.fuse_process = multiprocessing.Process(
            target=fuse.FUSE,
            args=(PyfilesystemFuseOperations(self.source_fs), self.mountpoint),
            kwargs={"foreground": True, "debug": False},
        )
        self._mount()
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

class TestFuseMemFS(_TestFuseMount, unittest.TestCase):
    _source_url = "mem://"

class TestFuseMountTempFS(_TestFuseMount, unittest.TestCase):
    _source_url = "temp://"




class TestAtomicOperations(unittest.TestCase):

    def setUp(self):
        self.fs = fs.open_fs('mem://')
        self.ops = PyfilesystemFuseOperations(self.fs)

    def test_miscellaneous(self):
        with self.assertRaises(OSError) as handler:
            self.ops.getxattr('/', None)
        self.assertEqual(handler.exception.errno, errno.ENOTSUP)
        with self.assertRaises(OSError) as handler:
            self.ops.link('a', 'b')
        self.assertEqual(handler.exception.errno, errno.EPERM)
        with self.assertRaises(OSError) as handler:
            self.ops.symlink('a', 'b')
        self.assertEqual(handler.exception.errno, errno.EPERM)
        with self.assertRaises(OSError) as handler:
            self.ops('unknown')
        self.assertEqual(handler.exception.errno, errno.ENOSYS)

    def test_chmod(self):
        # Normal behaviour
        # Cannot test because MemoryFS do not support chmod
        # self.fs.create('file.txt')
        # self.ops.chmod('file.txt', 0o700)
        # self.assertEqual(
        #     self.fs.getinfo('file.txt', ['access']).permissions.mode,
        #     0o700
        # )
        # self.ops.chmod('file.txt', 0o600)
        # self.assertEqual(
        #     self.fs.getinfo('file.txt', ['access']).permissions.mode,
        #     0o700
        # )
        # Error on non-existing path
        with self.assertRaises(OSError) as ctx:
            self.ops.chmod('unknown', 0)
        self.assertEqual(ctx.exception.errno, errno.ENOENT)

    def test_chown(self):
        # Normal behaviour
        # Cannot test because MemoryFS do not support chmod
        # self.fs.create('file.txt')
        # self.ops.chown('file.txt', 0, 1)
        # self.assertEqual(
        #     self.fs.getinfo('file.txt', ['access']).uid, 0)
        # self.assertEqual(
        #     self.fs.getinfo('file.txt', ['access']).gid, 0)
        # Error on non-existing path
        with self.assertRaises(OSError) as ctx:
            self.ops.chown('unknown', 0, 1)
        self.assertEqual(ctx.exception.errno, errno.ENOENT)


    def test_close(self):
        self.fs.create('file.txt')
        # Normal behaviour
        fd = self.ops('open', 'file.txt', posix.O_RDONLY)

    def test_create(self):
        self.assertFalse(self.fs.exists('file.txt'))
        # Normal behaviour
        fd = self.ops('create', 'file.txt', 0)
        self.assertEqual(fd, 0)
        self.assertTrue(self.fs.exists('file.txt'))
        fd2 = self.ops('create', 'file.txt', 0)
        self.assertEqual(fd2, 1)
        # Error when the file exists in exclusive mode
        with self.assertRaises(OSError) as ctx:
            self.ops('create', 'file.txt', posix.O_EXCL)
        self.assertEqual(ctx.exception.errno, errno.EEXIST)
        # Error when creating an existing directory
        self.fs.makedir('/dir')
        with self.assertRaises(OSError) as ctx:
            self.ops('create', 'dir', 0)
        self.assertEqual(ctx.exception.errno, errno.EISDIR)

    def test_destroy(self):
        self.fs.create('test.txt')
        fd = self.ops.open('test.txt', posix.O_RDONLY)
        fh = self.ops.descriptors[fd]
        self.assertFalse(fh.closed)
        self.assertFalse(self.fs.isclosed())
        self.ops.destroy('/')
        self.assertTrue(self.fs.isclosed())
        self.assertTrue(fh.closed)
        self.assertNotIn(fd, self.ops.descriptors)

    def test_flush(self):
        # Normal behaviour
        fd = self.ops.create('abc', posix.O_RDWR)
        self.ops.flush('abc', fd)
        # Error on bad file descriptor
        with self.assertRaises(OSError) as handler:
            self.ops('flush', 'abc', fd+1)
        self.assertEqual(handler.exception.errno, errno.EBADF)

    def test_getattr(self):

        umask = os.umask(0)
        os.umask(umask)

        test_data = [
            (
                {'details': {'accessed': 0}},
                {'st_atime': 0, 'st_mode': stat.S_IFREG}
            ),
            (
                {'details': {'modified': 0}},
                {'st_mtime': 0, 'st_mode': stat.S_IFREG}
            ),
            (
                {'details': {'size': 100}},
                {'st_size': 100, 'st_mode': stat.S_IFREG}
            ),
            (
                {'details': {'created': 0, 'type': int(ResourceType.directory)}},
                {'st_ctime': 0, 'st_mode': stat.S_IFDIR}
            ),
            (
                {'access': {'uid': 0, 'gid': 0}},
                {'st_uid': 0, 'st_gid': 0}
            ),
            (
                {'stat': {'st_mode': 17407, 'st_ino': 2947, 'st_dev': 42}},
                {'st_mode': 17407, 'st_ino': 2947, 'st_dev': 42}
            ),
            (
                {'access': {'permissions': ['u_r', 'u_w']}},
                {'st_mode': 0o600}
            ),
            (
                {'details': {'type': ResourceType.directory}, 'access': {}},
                {'st_mode': stat.S_IFDIR | 0o777 & ~umask},
            ),
            (
                {'details': {'type': ResourceType.file}, 'access': {}},
                {'st_mode': stat.S_IFREG | 0o666 & ~umask},
            ),
            (
                {'basic': {'name': ''}},
                {'st_nlink': 2}
            )
        ]

        for i, statd in test_data:
            statinfo = PyfilesystemFuseOperations._stat_from_info(Info(i))
            self.assertEqual(statd, statinfo)

        self.fs.create('abc.txt')
        self.assertTrue(self.ops.getattr('abc.txt'))

    def test_makedir(self):
        # Normal behaviour
        self.assertFalse(self.fs.isdir('test'))
        self.ops('mkdir', 'test', None)
        self.assertTrue(self.fs.isdir('test'))
        # Error when given an existing path
        with self.assertRaises(OSError) as handler:
            self.ops('mkdir', 'test', None)
        self.assertEqual(handler.exception.errno, errno.EEXIST)
        # Error when invalid path
        with self.assertRaises(OSError) as handler:
            self.ops('mkdir', 'test\0', None)
        self.assertEqual(handler.exception.errno, errno.EINVAL)
        # Error when a component does not exist
        with self.assertRaises(OSError) as handler:
            self.ops('mkdir', 'parent/test', None)
        self.assertEqual(handler.exception.errno, errno.ENOENT)
        # Error when read-only
        self.ops.fs = read_only(self.ops.fs)
        with self.assertRaises(OSError) as handler:
            self.ops('mkdir', 'parent/test', None)
        self.assertEqual(handler.exception.errno, errno.EROFS)
        # Error when a component is not a file
        # FIXME: must fix MemoryFS to raise the right error
        #        and not an AssertionError
        # self.fs.touch('abc.txt')
        # with self.assertRaises(OSError) as handler:
        #     self.ops('mkdir', 'abc.txt/test', None)
        # self.assertEqual(handler.exception.errno, errno.ENOTDIR)

    def test_read(self):
        self.fs.settext('file.txt', 'Hello, World!')
        # Normal behaviour
        fd = self.ops('open', 'file.txt', posix.O_RDONLY)
        self.assertEqual(self.ops('read', 'file.txt', 100, 0, fd), b'Hello, World!')
        self.assertEqual(self.ops('read', 'file.txt', 10, 0, fd), b'Hello, Wor')
        self.assertEqual(self.ops('read', 'file.txt', 10, 3, fd), b'lo, World!')
        # Error on bad file descriptor
        with self.assertRaises(OSError) as handler:
            self.ops('read', 'file.txt', 10, 0, fd+1)
        self.assertEqual(handler.exception.errno, errno.EBADF)
        # Error on not readable
        fd = self.ops('open', 'file.txt', posix.O_WRONLY)
        with self.assertRaises(OSError) as handler:
            self.ops('read', 'file.txt', 10, 0, fd)
        self.assertEqual(handler.exception.errno, errno.EINVAL)

    def test_readdir(self):
        # Normal behaviour
        self.assertEqual(self.ops('readdir', '/', None), ['.', '..'])
        self.fs.makedirs('top/middle/bottom')
        self.fs.touch('root.txt')
        self.fs.touch('top/file.bin')
        self.assertEqual(
            sorted(x[0] if isinstance(x, tuple) else x
               for x in self.ops('readdir', '/', None)),
            ['.', '..', 'root.txt', 'top']
        )
        self.assertEqual(
            sorted(x[0] if isinstance(x, tuple) else x
                   for x in self.ops('readdir', 'top', None)),
            ['.', '..', 'file.bin', 'middle']
        )
        self.assertEqual(
            sorted(x[0] if isinstance(x, tuple) else x
                   for x in self.ops('readdir', 'top/middle/bottom', None)),
            ['.', '..']
        )
        # Error when given path is not a directory
        with self.assertRaises(OSError) as handler:
            self.ops('readdir', 'root.txt', None)
        self.assertEqual(handler.exception.errno, errno.ENOTDIR)
        # Error on non-existing path
        with self.assertRaises(OSError) as handler:
            self.ops('readdir', 'foo/bar', None)
        self.assertEqual(handler.exception.errno, errno.ENOENT)

    def test_release(self):
        self.fs.touch('test.txt')
        fd = self.ops.open('test.txt', posix.O_RDWR)
        self.assertIn(fd, self.ops.descriptors)
        fh = self.ops.descriptors[fd]
        self.assertFalse(fh.closed)
        self.ops('release', 'test.txt', fd)
        self.assertNotIn(fd, self.ops.descriptors)
        self.assertTrue(fh.closed)
        with self.assertRaises(OSError) as handler:
            self.ops('release', 'test.txt', fd)
        self.assertEqual(handler.exception.errno, errno.EBADF)

    def test_rename_file(self):
        # Normal behaviour
        self.fs.settext('abc.txt', 'ABC')
        self.assertFalse(self.fs.exists('file.txt'))
        self.ops('rename', 'abc.txt', 'file.txt')
        self.assertFalse(self.fs.exists('abc.txt'))
        self.assertTrue(self.fs.exists('file.txt'))
        self.assertEqual(self.fs.gettext('file.txt'), 'ABC')
        # Error on non existing old path
        with self.assertRaises(OSError) as handler:
            self.ops('rename', 'foo', 'bar')
        self.assertEqual(handler.exception.errno, errno.ENOENT)
        # Error on empty source or destination
        with self.assertRaises(OSError) as handler:
            self.ops('rename', '', 'bar')
        self.assertEqual(handler.exception.errno, errno.ENOENT)
        # Error on bad component in file name
        with self.assertRaises(OSError) as handler:
            self.ops('rename', 'file.txt/foo', 'bar')
        self.assertEqual(handler.exception.errno, errno.ENOTDIR)

    def test_rename_directory(self):
        # Normal behaviour
        self.fs.makedir('a')
        self.fs.settext('a/abc.txt', 'ABC')
        self.fs.settext('a/def.txt', 'DEF')
        self.ops('rename', 'a', 'b')
        self.assertFalse(self.fs.exists('a'))
        self.assertTrue(self.fs.exists('b'))
        self.assertEqual(sorted(self.fs.listdir('b')), ['abc.txt', 'def.txt'])
        # Error when moving a file to a directory
        self.fs.makedir('c')
        with self.assertRaises(OSError) as handler:
            self.ops('rename', 'b/abc.txt', 'c')
        self.assertEqual(handler.exception.errno, errno.EISDIR)
        # Error when moving a directory inside itself
        self.fs.makedir('b/b2')
        with self.assertRaises(OSError) as handler:
            self.ops('rename', 'b', 'b/b2')
        self.assertEqual(handler.exception.errno, errno.EINVAL)
        # Error when moving a directory to a non-empty directory
        self.fs.touch('c/bar')
        with self.assertRaises(OSError) as handler:
            self.ops('rename', 'b', 'c')
        self.assertEqual(handler.exception.errno, errno.ENOTEMPTY)

    def test_rmdir(self):
        # Normal behaviour
        self.fs.makedir('a')
        self.assertTrue(self.fs.exists('a') and self.fs.isdir('a'))
        self.ops('rmdir', 'a')
        self.assertFalse(self.fs.exists('a'))
        # Error when removing a non empty directory
        self.fs.makedir('a')
        self.fs.touch('a/b')
        with self.assertRaises(OSError) as handler:
            self.ops('rmdir', 'a')
        self.assertEqual(handler.exception.errno, errno.ENOTEMPTY)
        # Error when removing an non-existing directory
        with self.assertRaises(OSError) as handler:
            self.ops('rmdir', 'c')
        self.assertEqual(handler.exception.errno, errno.ENOENT)
        # Error when removing a file
        with self.assertRaises(OSError) as handler:
            self.ops('rmdir', 'a/b')
        self.assertEqual(handler.exception.errno, errno.ENOTDIR)
        # Error on a bad component in the path
        self.fs.touch('file.txt')
        with self.assertRaises(OSError) as handler:
            self.ops('rmdir', 'a/b/c')
        self.assertEqual(handler.exception.errno, errno.ENOTDIR)

    def test_statfs(self):
        with mock.patch.dict(self.fs._meta, {}):
            self.assertEqual(self.ops.statfs('/'), {})
        with mock.patch.dict(self.fs._meta, {'max_sys_path_length': 1}):
            self.assertEqual(self.ops.statfs('/'), {'f_namelen': 1})

    def test_truncate(self):
        # Normal behaviour
        self.fs.settext('file.txt', 'Hello, World !')
        self.ops('truncate', 'file.txt', 5)
        self.assertEqual(self.fs.gettext('file.txt'), 'Hello')
        # Normal behaviour on open file
        fd = self.ops.open('file.txt', posix.O_RDWR)
        self.ops('truncate', 'file.txt', 2, fd)
        self.assertEqual(self.fs.gettext('file.txt'), 'He')
        # Normal behaviour when extending file
        self.ops('truncate', 'file.txt', 4, fd)
        self.assertEqual(self.fs.gettext('file.txt'), 'He\0\0')
        # Error on unknown descriptor
        with self.assertRaises(OSError) as ctx:
            self.ops('truncate', 'file.txt', 0, 5)
        self.assertEqual(ctx.exception.errno, errno.EBADF)
        # Error when fd does not refer to path
        # Requires _MemoryFile.name attribute
        # with self.assertRaises(OSError) as ctx:
        #     self.ops('truncate', 'dir', 0, fd)
        # self.assertEqual(ctx.exception.errno, errno.EBADF)
        # Error when trying to truncate a directory
        self.fs.makedir('dir')
        with self.assertRaises(OSError) as ctx:
            self.ops('truncate', 'dir', 0)
        self.assertEqual(ctx.exception.errno, errno.EISDIR)
        # Error when truncating a file from a read-only descriptor
        fd = self.ops.open('file.txt', posix.O_RDONLY)
        with self.assertRaises(OSError) as ctx:
            self.ops('truncate', 'file.txt', 0, fd)
        self.assertEqual(ctx.exception.errno, errno.EINVAL)

    def test_unlink(self):
        self.fs.create('file.txt')
        # Normal behaviour
        self.ops('unlink', 'file.txt')
        self.assertFalse(self.fs.exists('file.txt'))
        # Error when the target does not exist
        with self.assertRaises(OSError) as handler:
            self.ops('unlink', 'file.txt')
        self.assertEqual(handler.exception.errno, errno.ENOENT)
        # Error when trying to unlink a directory
        self.fs.makedir('test')
        with self.assertRaises(OSError) as handler:
            self.ops('unlink', 'test')
        self.assertEqual(handler.exception.errno, errno.EISDIR)
        # Error when one of the components in the path is not a directory
        self.fs.create('abc')
        with self.assertRaises(OSError) as handler:
            self.ops('unlink', 'abc/def')
        self.assertEqual(handler.exception.errno, errno.ENOTDIR)
        # Error when the filesystem is read-only
        self.ops.fs = read_only(self.fs)
        with self.assertRaises(OSError) as handler:
            self.ops('unlink', 'create')
        self.assertEqual(handler.exception.errno, errno.EROFS)

    def test_utimens(self):
        self.fs.create('file.txt')
        # Normal behaviour
        self.ops.utimens('file.txt', (0, 0))
        info = self.fs.getdetails('file.txt')
        self.assertEqual(timestamp(info.accessed), 0)
        self.assertEqual(timestamp(info.modified), 0)
        # Error on unknown file
        with self.assertRaises(OSError) as handler:
            self.ops.utimens('unknown.txt')
        self.assertEqual(handler.exception.errno, errno.ENOENT)

    def test_write(self):
        # Normal behaviour
        fd = self.ops.open('test.txt', posix.O_CREAT | posix.O_WRONLY)
        self.ops.write('test.txt', b'Hello, ', 0, fd)
        self.ops.write('test.txt', b'World!', 7, fd)
        self.ops.release('test.txt', fd)
        self.assertEqual(self.fs.getbytes('test.txt'), b'Hello, World!')
        # Error on bad file descriptor
        with self.assertRaises(OSError) as ctx:
            self.ops('write', 'file.txt', b'', 0, fd+1)
        self.assertEqual(ctx.exception.errno, errno.EBADF)
        # Error when writing to a file that is not open for writing
        fd = self.ops.open('test.txt', posix.O_RDONLY)
        with self.assertRaises(OSError) as ctx:
            self.ops('write', 'file.txt', b'', 0, fd)
        self.assertEqual(ctx.exception.errno, errno.EINVAL)
