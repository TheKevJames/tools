import ../src/spacerep


proc test_sm2() =
    let val = sm2([2.cint,1.cint,3.cint,3.cint,4.cint,1.cint,2.cint,3.cint,4.cint])
    echo val
    doAssert abs(val - 9.4583) < 1E-4


when isMainModule:
    test_sm2()
