#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import errno
import os
import sys


def is_pathname_valid(pathname: str) -> bool:
    """Checks if the path provided is valid for the current OS. Returns True if valid, False if invalid."""
    ERROR_INVALID_NAME = 123
    try:
        if not isinstance(pathname, str) or not pathname:
            return False
        _, pathname = os.path.splitdrive(pathname)
        root_dirname = (
            os.environ.get("HOMEDRIVE", "C:")
            if sys.platform == "win32"
            else os.path.sep
        )
        assert os.path.isdir(root_dirname)
        root_dirname = root_dirname.rstrip(os.path.sep) + os.path.sep
        for pathname_part in pathname.split(os.path.sep):
            try:
                os.lstat(root_dirname + pathname_part)
            except OSError as exc:
                if hasattr(exc, "winerror"):
                    if exc.winerror == ERROR_INVALID_NAME:
                        return False
                elif exc.errno in {errno.ENAMETOOLONG, errno.ERANGE}:
                    return False
    except TypeError:
        return False
    else:
        return True


def is_path_creatable(pathname: str) -> bool:
    """Checks if the path is creatable by the user (permissions/access check). Returns True if current user is able to create the path, False otherwise."""
    dirname = os.path.dirname(pathname) or os.getcwd()
    return os.access(dirname, os.W_OK)


def is_path_exists_or_creatable(pathname: str) -> bool:
    """Checks both the conditions specified above."""
    try:
        return is_pathname_valid(pathname) and (
            os.path.exists(pathname) or is_path_creatable(pathname)
        )
    except OSError:
        return False
