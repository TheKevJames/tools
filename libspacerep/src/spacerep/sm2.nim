import math
import sequtils

# TODO: exportc can't export default values
proc sm2*(xs: openarray[cint],
          a: cfloat = 6.0,
          b: cfloat = -0.8,
          c: cfloat = 0.28,
          d: cfloat = 0.02,
          theta: cfloat = 0.2): cfloat {.exportc: "sm2".} =
    proc sm2poly(x: cint): float = b + c * x.float + d * x.float * x.float

    if xs[^1] < 3:
        return 1

    var consecutive = 0.0
    for i in countdown(high(xs), low(xs)):
        if xs[i] < 3:
            break
        consecutive += 1

    let solvedpoly = math.sum(xs.map(sm2poly))
    return a * math.pow(max([1.3, 2.5 + solvedpoly]), theta * consecutive)
