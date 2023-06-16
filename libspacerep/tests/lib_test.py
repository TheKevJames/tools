import pytest

from libspacerep import lib  # pylint: disable=no-name-in-module


@pytest.mark.parametrize(
    'xs, expected',
    [
        ([2, 1, 3, 3, 4, 1, 2, 3, 4], 9.4583),
        ([3], 7.3293),
        ([3, 1, 5, 3, 5], 15.0682),
        ([0, 0, 1], 1.0),
        ([0], 1.0),
        ([0, 0, 1, 2], 1.0),
        ([0, 1, 2, 3], 6.3232),
        ([0, 1, 2, 3, 3], 7.0187),
        ([0, 1, 2, 3, 2], 1.0),
        ([0, 1, 2, 3, 3, 5], 10.5955),
        ([5, 5, 5, 5, 5, 5, 5], 154.9500),
    ],
)
def test_sm2(xs, expected):
    lib.NimMain()
    val = lib.sm2(xs, len(xs), 6.0, -0.8, 0.28, 0.02, 1.3, 2.5, 0.2)
    print(val)
    assert abs(val - expected) < 0.0001
