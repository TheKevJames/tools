#!/usr/bin/env python3
import pathlib

import cffi


builder = cffi.FFI()
builder.cdef('int fib(int n);')
builder.set_source('libspacerep',
                   '#include "spacerep.h"',
                   sources=(pathlib.Path() / 'build').glob('**/*.c'),
                   include_dirs=['/usr/lib/nim', './build'])


if __name__ == '__main__':
    builder.compile(verbose=True)
