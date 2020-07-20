version       = "0.1.0"
author        = "Kevin James"
description   = "Spaced Repetition library"
license       = "MIT"

srcDir = "src"

requires "nim >= 0.17.2"

task make, "Compiles shared library":
    exec "nim c --nimcache:build/ --noMain --noLinking -d:release --opt:speed --header src/spacerep.nim"
