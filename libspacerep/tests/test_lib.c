#include "spacerep.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>


int main(void) {
    NimMain();
    int xs[9] = {2,1,3,3,4,1,2,3,4};
    float val = sm2(xs, 9, 6.0, -0.8, 0.28, 0.02, 1.3, 2.5, 0.2);
    if (fabs(val - 9.4583) >= 0.0001) {
        printf("%.4f\n", val);
    }
    assert(fabs(val - 9.4583) < 0.0001);
    printf("\033[32;1mOK:\033[0m All tests passed!\n");
    return 0;
}
