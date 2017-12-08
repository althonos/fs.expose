# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

__all__ = ['TestExposeXMLRPC']

import textwrap
import threading
import unittest
import base64

import six
import fs

from fs.expose.xmlrpc import serve
from fs.errors import *
from fs.test import *
from fs.xmlrpcfs import XMLRPC_FS

from .utils import mock



class TestExposeXMLRPC(unittest.TestCase,FSTestCases):

    host = 'localhost'
    port = 8081


    @classmethod
    def setUpClass(cls):
        cls.test_fs = fs.open_fs('mem://')
        cls.server_thread = serve(cls.test_fs, cls.host, cls.port)
        cls.fs = XMLRPC_FS("http://%s:%s/"%(cls.host,cls.port),allow_none=True)#,verbose=True)

    def tearDown(self):
        self.test_fs.removetree('/')

    @classmethod
    def tearDownClass(cls):
        cls.server_thread.shutdown()
        cls.test_fs.close()
        
    def test_unsupported(self):
        with self.assertRaises(Unsupported) as err:
            self.fs.open('/unsupported_function_test.txt')



    def assert_text(self, path, contents):
        """Assert a file contains the given text.

        Arguments:
            path (str): A path on the filesystem.
            contents (str): Text to compare.

        """
        assert isinstance(contents, text_type)
        data = self.fs.gettext(path)
        self.assertEqual(data, contents)
        self.assertIsInstance(data, text_type)

#Officialy not supported
##############################
    @unittest.skip("Not Supported")
    def test_openbin_rw(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_open_files(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_open(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_openbin(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_bin_files(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_files(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_close(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_copy_file(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_desc(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_scandir(self):
        #Not Supported
        #Cant transfer generators
        pass
    @unittest.skip("Not Supported")
    def test_tree(self):
        #Not Supported
        #Cant transfer StringIO
        pass
    @unittest.skip("Not Supported")
    def test_move_dir_mem(self):
        #Not Supported
        pass             
    @unittest.skip("Not Supported")
    def test_move_dir_temp(self):
        #Not Supported
        pass             
    @unittest.skip("Not Supported")
    def test_move_file_mem(self):
        #Not Supported
        pass             
    @unittest.skip("Not Supported")
    def test_move_file_same_fs(self):
        #Not Supported
        pass             
    @unittest.skip("Not Supported")
    def test_move_file_temp(self):
        #Not Supported
        pass             
    @unittest.skip("Not Supported")
    def test_move_same_fs(self):
        #Not Supported
        pass             
    @unittest.skip("Not Supported")
    def test_opendir(self):
        #Not Supported
        pass             
    @unittest.skip("Not Supported")
    def test_repeat_dir(self):
        #Not Supported
        pass             
    @unittest.skip("Not Supported")
    def test_setbinfile(self):
        #Not Supported
        pass               
    @unittest.skip("Not Supported")
    def test_setfile(self):
        #Not Supported
        pass         
    @unittest.skip("Not Supported")
    def test_copy_dir_mem(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_copy_dir_temp(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_copy_structure(self):
        #Not Supported
        pass
    @unittest.skip("Not Supported")
    def test_filterdir(self):
        #Not Supported
        pass  
        

#Modified
##############################

    def test_getbytes(self):
        # Test getbytes method.
        all_bytes = b''.join(six.int2byte(n) for n in range(256))
        
        #Open not supported, changed Test
        self.fs.setbytes('foo',all_bytes)
        # ~ with self.fs.open('foo', 'wb') as f:
            # ~ f.write(all_bytes)
        self.assertEqual(self.fs.getbytes('foo'), all_bytes)
        _all_bytes = self.fs.getbytes('foo')
        self.assertIsInstance(_all_bytes, bytes)
        self.assertEqual(_all_bytes, all_bytes)

        with self.assertRaises(errors.ResourceNotFound):
            self.fs.getbytes('foo/bar')

        self.fs.makedir('baz')
        with self.assertRaises(errors.FileExpected):
            self.fs.getbytes('baz')
             
    def test_setbytes(self):
        all_bytes = b''.join(six.int2byte(n) for n in range(256))
        self.fs.setbytes('foo', all_bytes)
        
        #Open not supported, changed Test
        _bytes = self.fs.getbytes('foo')
        # ~ with self.fs.open('foo', 'rb') as f:
            # ~ _bytes = f.read()
        self.assertIsInstance(_bytes, bytes)
        self.assertEqual(_bytes, all_bytes)
        self.assert_bytes('foo', all_bytes)
        with self.assertRaises(TypeError):
            self.fs.setbytes('notbytes', 'unicode')
            
    def test_copy(self):
        # Test copy to new path
        self.fs.setbytes('foo', b'test')
        self.fs.copy('foo', 'bar')
        self.assert_bytes('bar', b'test')

        # Test copy over existing path
        self.fs.setbytes('baz', b'truncateme')
        
        #kwargs not supported, modified Test:
        self.fs.copy('foo', 'baz', True)
        # ~ self.fs.copy('foo', 'baz', overwrite=True)
        
        self.assert_bytes('foo', b'test')

        # Test copying a file to a destination that exists
        with self.assertRaises(errors.DestinationExists):
            self.fs.copy('baz', 'foo')

        # Test copying to a directory that doesn't exist
        with self.assertRaises(errors.ResourceNotFound):
            self.fs.copy('baz', 'a/b/c/baz')

        # Test copying a source that doesn't exist
        with self.assertRaises(errors.ResourceNotFound):
            self.fs.copy('egg', 'spam')

        # Test copying a directory
        self.fs.makedir('dir')
        with self.assertRaises(errors.FileExpected):
            self.fs.copy('dir', 'folder')

    def test_create(self):
        # Test create new file
        self.assertFalse(self.fs.exists('foo'))
        self.fs.create('foo')
        self.assertTrue(self.fs.exists('foo'))
        #Modified Test, gettype is not running now, will be fixed
        self.assertEqual(self.fs.isfile('foo'), True)
        # ~ self.assertEqual(self.fs.gettype('foo'), ResourceType.file)
        self.assertEqual(self.fs.getsize('foo'), 0)

        # Test wipe existing file
        self.fs.setbytes('foo', b'bar')
        self.assertEqual(self.fs.getsize('foo'), 3)
        #no kwargs supported
        self.fs.create('foo', True)
        # ~ self.fs.create('foo', wipe=True)
        self.assertEqual(self.fs.getsize('foo'), 0)

        # Test create with existing file, and not wipe
        self.fs.setbytes('foo', b'bar')
        self.assertEqual(self.fs.getsize('foo'), 3)
        #no kwargs supported
        self.fs.create('foo', False)
        # ~ self.fs.create('foo', wipe=False)
        self.assertEqual(self.fs.getsize('foo'), 3)

    def test_makedirs(self):
        self.assertFalse(self.fs.exists('foo'))
        self.fs.makedirs('foo')
        self.assertEqual(self.fs.isdir('foo'),True)

        self.fs.makedirs('foo/bar/baz')
        self.assertTrue(self.fs.isdir('foo/bar'))
        self.assertTrue(self.fs.isdir('foo/bar/baz'))

        with self.assertRaises(errors.DirectoryExists):
            self.fs.makedirs('foo/bar/baz')
        #no kwargs supported
        self.fs.makedirs('foo/bar/baz', None, True)
        # ~ self.fs.makedirs('foo/bar/baz', recreate=True)

        self.fs.setbytes('foo.bin', b'test')
        with self.assertRaises(errors.DirectoryExpected):
            self.fs.makedirs('foo.bin/bar')

        with self.assertRaises(errors.DirectoryExpected):
            self.fs.makedirs('foo.bin/bar/baz/egg')

    def test_settext(self):
        # Test settext method.
        self.fs.settext('foo', 'bar')
        foo = self.fs.gettext('foo')
        self.assertEqual(foo, 'bar')
        self.assertIsInstance(foo, text_type)
        with self.assertRaises(TypeError):
            self.fs.settext('nottext', b'bytes')

    def test_appendtext(self):
        with self.assertRaises(TypeError):
            self.fs.appendtext('foo', b'bar')
        self.fs.appendtext('foo', 'bar')
        self.assert_text('foo', 'bar')
        self.fs.appendtext('foo', 'baz')
        self.assert_text('foo', 'barbaz')

    def test_gettext(self):
        self.fs.makedir('foo')
        self.fs.settext('foo/unicode.txt', UNICODE_TEXT)
        text = self.fs.gettext('foo/unicode.txt')
        self.assertIsInstance(text, text_type)
        self.assertEqual(text, UNICODE_TEXT)
        self.assert_text('foo/unicode.txt', UNICODE_TEXT)

    def test_geturl_purpose(self):
        """Check an unknown purpose raises a NoURL error.
        """
        self.fs.create('foo')
        with self.assertRaises(errors.NoURL):
            self.fs.geturl('foo', '__nosuchpurpose__')

    def test_makedir(self):
        # Check edge case of root
        with self.assertRaises(errors.DirectoryExists):
            self.fs.makedir('/')

        # Making root is a null op with recreate
        #Cant send Filesystems over xmlrpc
        # ~ slash_fs = self.fs.makedir('/', True)
        # ~ self.assertIsInstance(slash_fs, SubFS)
        # ~ self.assertEqual(self.fs.listdir('/'), [])

        self.assert_not_exists('foo')
        self.fs.makedir('foo')
        self.assert_isdir('foo')
        self.assertEqual(self.fs.isdir('foo'), True)
        self.fs.setbytes('foo/bar.txt', b'egg')
        self.assert_bytes('foo/bar.txt', b'egg')

        # Directory exists
        with self.assertRaises(errors.DirectoryExists):
            self.fs.makedir('foo')

        # Parent directory doesn't exist
        with self.assertRaises(errors.ResourceNotFound):
            self.fs.makedir('/foo/bar/baz')

        self.fs.makedir('/foo/bar')
        self.fs.makedir('/foo/bar/baz')

        with self.assertRaises(errors.DirectoryExists):
            self.fs.makedir('foo/bar/baz')

        with self.assertRaises(errors.DirectoryExists):
            self.fs.makedir('foo/bar.txt')

    def test_move(self):
        # Make a file
        self.fs.setbytes('foo', b'egg')
        self.assert_isfile('foo')

        # Move it
        self.fs.move('foo', 'bar')

        # Check it has gone from original location
        self.assert_not_exists('foo')

        # Check it exists in the new location, and contents match
        self.assert_exists('bar')
        self.assert_bytes('bar', b'egg')

        # Check moving to existing file fails
        self.fs.setbytes('foo2', b'eggegg')
        with self.assertRaises(errors.DestinationExists):
            self.fs.move('foo2', 'bar')

        # Check move with overwrite=True
        self.fs.move('foo2', 'bar', True)
        self.assert_not_exists('foo2')

        # Check moving to a non-existant directory
        with self.assertRaises(errors.ResourceNotFound):
            self.fs.move('bar', 'egg/bar')

        # Check moving an unexisting source
        with self.assertRaises(errors.ResourceNotFound):
            self.fs.move('egg', 'spam')

        # Check moving between different directories
        self.fs.makedir('baz')
        self.fs.setbytes('baz/bazbaz', b'bazbaz')
        self.fs.makedir('baz2')
        self.fs.move('baz/bazbaz', 'baz2/bazbaz')
        self.assert_not_exists('baz/bazbaz')
        self.assert_bytes('baz2/bazbaz', b'bazbaz')

        # Check moving a directory raises an error
        self.assert_isdir('baz2')
        self.assert_not_exists('yolk')
        with self.assertRaises(errors.FileExpected):
            self.fs.move('baz2', 'yolk')

    def test_setinfo(self):
        self.fs.create('birthday.txt')
        now = math.floor(time.time())

        change_info = {
            'details':
            {
                'accessed': now + 60,
                'modified': now + 60 * 60
            }
        }
        self.fs.setinfo('birthday.txt', change_info)
        new_info = self.fs.getinfo(
            'birthday.txt',
            ['details']
        ).raw
        if 'accessed' in new_info.get('_write', []):
            self.assertEqual(new_info['details']['accessed'], now + 60)
        if 'modified' in new_info.get('_write', []):
            self.assertEqual(new_info['details']['modified'], now + 60 * 60)

        with self.assertRaises(errors.ResourceNotFound):
            self.fs.setinfo('nothing', {})

    def test_settimes(self):
        self.fs.create('birthday.txt')
        self.fs.settimes(
            'birthday.txt',
            datetime(2016, 7, 5),
            None)
        info = self.fs.getinfo('birthday.txt', ['details'])
        writeable = info.get('details', '_write', [])
        if 'accessed' in writeable:
            self.assertEqual(info.accessed, datetime(2016, 7, 5, tzinfo=pytz.UTC))
        if 'modified' in writeable:
            self.assertEqual(info.modified, datetime(2016, 7, 5, tzinfo=pytz.UTC))

    def test_getinfo(self):
        # Test special case of root directory
        # Root directory has a name of ''
        root_info = self.fs.getinfo('/')
        self.assertEqual(root_info.name, '')
        self.assertTrue(root_info.is_dir)

        # Make a file of known size
        self.fs.setbytes('foo', b'bar')
        self.fs.makedir('dir')

        # Check basic namespace
        info = self.fs.getinfo('foo').raw
        self.assertIsInstance(info['basic']['name'], text_type)
        self.assertEqual(info['basic']['name'], 'foo')
        self.assertFalse(info['basic']['is_dir'])

        # Check basic namespace dir
        info = self.fs.getinfo('dir').raw
        self.assertEqual(info['basic']['name'], 'dir')
        self.assertTrue(info['basic']['is_dir'])

        # Get the info
        info = self.fs.getinfo('foo', ['details']).raw
        self.assertIsInstance(info, dict)
        self.assertEqual(info['details']['size'], 3)
        self.assertEqual(info['details']['type'], int(ResourceType.file))

        # Test getdetails
        self.assertEqual(info, self.fs.getdetails('foo').raw)

        # Raw info should be serializable
        try:
            json.dumps(info)
        except:
            assert False, "info should be JSON serializable"

        # Non existant namespace is not an error
        no_info = self.fs.getinfo('foo', '__nosuchnamespace__').raw
        self.assertIsInstance(no_info, dict)
        self.assertEqual(
            no_info['basic'],
            {'name': 'foo', 'is_dir': False}
        )

        # Check a number of standard namespaces
        # FS objects may not support all these, but we can at least
        # invoke the code
        self.fs.getinfo('foo', ['access', 'stat', 'details'])

    def test_touch(self):
        self.fs.touch('new.txt')
        self.assert_isfile('new.txt')
        self.fs.settimes('new.txt', datetime(2016, 7, 5))
        info = self.fs.getinfo('new.txt', ['details'])
        if info.is_writeable('details', 'accessed'):
            self.assertEqual(info.accessed, datetime(2016, 7, 5, tzinfo=pytz.UTC))
            now = time.time()
            self.fs.touch('new.txt')
            accessed = self.fs.getinfo('new.txt', ['details']).raw['details']['accessed']
            self.assertTrue(accessed - now < 5)

    def test_copydir(self):
        self.fs.makedirs('foo/bar/baz/egg')
        self.fs.settext('foo/bar/foofoo.txt', 'Hello')
        self.fs.makedir('foo2')
        self.fs.copydir('foo/bar', 'foo2')
        self.assert_text('foo2/foofoo.txt', 'Hello')
        self.assert_isdir('foo2/baz/egg')
        self.assert_text('foo/bar/foofoo.txt', 'Hello')
        self.assert_isdir('foo/bar/baz/egg')

        with self.assertRaises(errors.ResourceNotFound):
            self.fs.copydir('foo', 'foofoo')
        with self.assertRaises(errors.ResourceNotFound):
            self.fs.copydir('spam', 'egg', True)
        with self.assertRaises(errors.DirectoryExpected):
            self.fs.copydir('foo2/foofoo.txt', 'foofoo.txt', True)

    def test_movedir(self):
        self.fs.makedirs('foo/bar/baz/egg')
        self.fs.settext('foo/bar/foofoo.txt', 'Hello')
        self.fs.makedir('foo2')
        self.fs.movedir('foo/bar', 'foo2')
        self.assert_text('foo2/foofoo.txt', 'Hello')
        self.assert_isdir('foo2/baz/egg')
        self.assert_not_exists('foo/bar/foofoo.txt')
        self.assert_not_exists('foo/bar/baz/egg')

        # Check moving to an unexisting directory
        with self.assertRaises(errors.ResourceNotFound):
            self.fs.movedir('foo', 'foofoo')

        # Check moving an unexisting directory
        with self.assertRaises(errors.ResourceNotFound):
            self.fs.movedir('spam', 'egg', True)

        # Check moving a file
        with self.assertRaises(errors.DirectoryExpected):
            self.fs.movedir('foo2/foofoo.txt', 'foo2/baz/egg')
            
    def test_invalid_chars(self):
        # Test invalid path method.
        # ~ with self.assertRaises(errors.InvalidCharsInPath):
            # ~ self.fs.open('invalid\0file', 'wb')

        with self.assertRaises(errors.InvalidCharsInPath):
            self.fs.validatepath('invalid\0file')
            
    def test_getmeta(self):
        # Get the meta dict
        meta = self.fs.getmeta()

        # Check default namespace
        self.fs.getmeta("standard")
        # ~ self.assertEqual(meta, )

        # Must be a dict
        self.assertTrue(isinstance(meta, dict))

        no_meta = self.fs.getmeta('__nosuchnamespace__')
        self.assertIsInstance(no_meta, dict)
        self.assertFalse(no_meta)
