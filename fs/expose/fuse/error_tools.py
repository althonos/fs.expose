# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import functools
import errno

import fuse
import six

from ... import errors


class _ConvertFSErrors(object):
    """Context manager and decorator to convert FSErrors in to FuseOSErrors.
    """

    FILE_ERRORS = {

        # errors.CreateFailed:,
        # errors.FilesystemClosed:,
        # errors.OperationFailed:,
        errors.InsufficientStorage: errno.ENOSPC,
        errors.OperationTimeout: errno.ETIMEDOUT,
        errors.PermissionDenied: errno.EACCES,
        errors.RemoteConnectionError: errno.ENONET,
        errors.RemoveRootError: errno.EPERM,
        errors.Unsupported: errno.ENOTSUP,
        # errors.PathError:,
        errors.InvalidPath: errno.EINVAL,
        errors.InvalidCharsInPath: errno.EINVAL,
        # errors.NoSysPath:,
        # errors.NoURL:,
        # errors.ResourceError:,
        errors.DestinationExists: errno.EEXIST,
        errors.DirectoryNotEmpty: errno.ENOTEMPTY,
        errors.FileExists: errno.EEXIST,
        # errors.ResourceInvalid:,
        errors.DirectoryExpected: errno.ENOTDIR,
        errors.FileExpected: errno.EISDIR,
        # errors.ResourceLocked:,
        errors.ResourceNotFound: errno.ENOENT,
        errors.ResourceReadOnly: errno.EROFS,

        errors.IllegalBackReference: errno.EINVAL,

        # errno.EACCES: errors.PermissionDenied,
        # errno.ESRCH: errors.ResourceNotFound,
        # errno.ENOTEMPTY: errors.DirectoryNotEmpty,
        # errno.EEXIST: errors.FileExists,
        # 183: errors.DirectoryExists,
        # #errno.ENOTDIR: errors.DirectoryExpected,
        # errno.ENOTDIR: errors.ResourceNotFound,
        # errno.ENAMETOOLONG: errors.PathError,
    }

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wrapper

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # if exc_type is not None:
        #     raise exc_value if exc_value else exc_type
        if exc_type is not None:
            if isinstance(exc_value, errors.FSError):
                six.reraise(
                    fuse.FuseOSError,
                    fuse.FuseOSError(self.FILE_ERRORS.get(exc_type)),
                    traceback
                )
            else:
                six.reraise(
                    exc_type, exc_value, traceback
                )

# Stops linter complaining about invalid class name
convert_fs_errors = _ConvertFSErrors()
