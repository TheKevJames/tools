# Package
version       = "0.1.0"
author        = "Kevin James"
description   = "Simple personal task manager"
license       = "MIT"

srcDir        = "src"
binDir        = "bin"
bin           = @["task"]

# Dependencies
requires "nim >= 1.6.2"
requires "cligen >= 1.5.23 & < 2.0.0"
