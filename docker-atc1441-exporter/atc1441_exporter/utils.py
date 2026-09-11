import array
import errno
import fcntl
import logging
import socket
import struct

logger = logging.getLogger(__name__)

# ioctl request codes from BlueZ's <bluetooth/hci_sock.h>:
#   HCIDEVUP   = _IOW('H', 201, int)
#   HCIDEVDOWN = _IOW('H', 202, int)
# Encoded as _IOW(type='H'=0x48, nr, size=sizeof(int)=4):
#   (dir=1 << 30) | (size << 16) | (type << 8) | nr
HCIDEVUP = 0x400448C9
HCIDEVDOWN = 0x400448CA


def toggle_device(interface: int, enable: bool) -> None:
    """Power ON or OFF a bluetooth device."""
    # TODO: figure out how to tell mypy this is a bluetooth socket
    # pylint: disable=no-member
    sock = socket.socket(
        socket.AF_BLUETOOTH,  # type: ignore[attr-defined, unused-ignore]
        socket.SOCK_RAW,
        socket.BTPROTO_HCI,  # type: ignore[attr-defined, unused-ignore]
    )
    # pylint: enable=no-member

    logger.info('toggling bluetooth device %d: %s', interface, enable)
    request = array.array('b', struct.pack('H', interface))
    try:
        fcntl.ioctl(
            sock.fileno(), HCIDEVUP if enable else HCIDEVDOWN, request[0]
        )
    except OSError as e:
        if e.errno != errno.EALREADY:
            raise
    finally:
        sock.close()
