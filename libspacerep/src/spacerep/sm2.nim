# TODO: https://github.com/walterscarborough/LibSpacey
import math
import sequtils

# with credit to: https://gist.github.com/doctorpangloss/13ab29abd087dc1927475e560f876797
proc sm2*(xs: openarray[cint],
          a: cfloat = 6.0,
          b: cfloat = -0.8,
          c: cfloat = 0.28,
          d: cfloat = 0.02,
          score_min: cfloat = 1.3,
          score_assumed: cfloat = 2.5,
          theta: cfloat = 0.2): cfloat {.exportc: "sm2".} =
    # TODO: faster as a macro?
    proc poly(x: cint): float = b + c * x.float + d * x.float * x.float

    if xs[^1] < 3:
        return 1.0

    var consecutive = 0.0
    for i in countdown(high(xs), low(xs)):
        if xs[i] < 3:
            break
        consecutive += 1

    let solved = math.sum(xs.map(poly))
    let base = max([score_min, score_assumed + solved])
    return a * math.pow(base, theta * consecutive)

# TODO: exportc can't export default values; how should we solve this?
# C doesn't support it either, how do c programmers handle this sorta thing?
# proc sm2*(xs: openarray[cint]): cfloat {.exportc: "sm2".} =
#     sm2(xs, 6.0, -0.8, 0.28, 0.02, 1.3, 2.5, 0.2)
