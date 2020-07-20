proc fib(n: cint): cint {.exportc.} =
    result =
        if n <= 2: 1
        else: fib(n - 1) + fib(n - 2)
