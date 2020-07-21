#!/usr/bin/env python3
import pathlib

import cffi


builder = cffi.FFI()
# TODO: can we call NimMain() automagically?
builder.cdef("""
    void NimMain();
    float sm2(int *xs, int xsize, float a, float b, float c, float d, float theta);
""")
builder.set_source('libspacerep',
                   '#include "spacerep.h"',
                   sources=(pathlib.Path() / 'build').glob('**/*.c'),
                   include_dirs=['/usr/lib/nim', './build'],
                   extra_compile_args=['-O2'])


if __name__ == '__main__':
    builder.compile(verbose=True)
