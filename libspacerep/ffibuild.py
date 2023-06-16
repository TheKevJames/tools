#!/usr/bin/env python3
# pylint: disable=line-too-long
import pathlib

import cffi


builder = cffi.FFI()
# TODO: can we call NimMain() automagically?
builder.cdef("""
    void NimMain();
    float sm2(int *xs, int xsize, float a, float b, float c, float d, float score_min, float score_assumed, float theta);
""")
builder.set_source(
    'libspacerep',
    '#include "spacerep.h"',
    sources=(pathlib.Path() / 'build').glob('**/*.c'),
    # TODO: how find correct lib dir?
    include_dirs=[
        './build',
        '/Users/kevin/.choosenim/toolchains/nim-1.2.4/lib',
        '/usr/lib/nim',
    ],
    extra_compile_args=['-O2'],
)


if __name__ == '__main__':
    builder.compile(verbose=True)
