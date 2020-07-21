import pytest
from libspacerep import lib


@pytest.mark.parametrize(
    'xs, expected',
    [
        ([2,1,3,3,4,1,2,3,4], 9.45),
    ])
def test_sm2(xs, expected):
    lib.NimMain()
    val = lib.sm2(xs, len(xs), 6.0, -0.8, 0.28, 0.02, 0.2)
    print(val)
    assert abs(val - 9.4583) < 0.0001
