import array
import errno
import fcntl
import logging
import socket
import struct
from collections.abc import Sequence
from typing import Optional
from typing import Protocol

from bluetooth._bluetooth import ba2str
from bluetooth._bluetooth import btsocket
from bluetooth._bluetooth import HCI_EVENT_PKT
from bluetooth._bluetooth import HCI_FILTER
from bluetooth._bluetooth import hci_filter_new
from bluetooth._bluetooth import hci_filter_set_event
from bluetooth._bluetooth import hci_filter_set_ptype
from bluetooth._bluetooth import hci_send_cmd
from bluetooth._bluetooth import HCIDEVDOWN
from bluetooth._bluetooth import HCIDEVUP
from bluetooth._bluetooth import SOL_HCI

# TODO: find a more recent bluetooth library which gives us the above
# TODO: do these get monkeypatched by the bluez import or something???
# pylint: disable=no-member
AF_BLUETOOTH = socket.AF_BLUETOOTH  # type: ignore[attr-defined]
BTPROTO_HCI = socket.BTPROTO_HCI  # type: ignore[attr-defined]
# pylint: enable=no-member


LE_PUBLIC_ADDRESS = 0x00
LE_RANDOM_ADDRESS = 0x01
LE_META_EVENT = 0x3E

# sub-events of LE_META_EVENT
EVT_LE_CONN_COMPLETE = 0x01
EVT_LE_ADVERTISING_REPORT = 0x02
EVT_LE_CONN_UPDATE_COMPLETE = 0x03
EVT_LE_READ_REMOTE_USED_FEATURES_COMPLETE = 0x04

SCAN_DISABLE = 0x00
SCAN_ENABLE = 0x01
SCAN_FILTER_DUPLICATES = 0x01
SCAN_TYPE_PASSIVE = 0x00

OGF_LE_CTL = 0x08
OCF_LE_SET_SCAN_PARAMETERS = 0x000B
OCF_LE_SET_SCAN_ENABLE = 0x000C
OCF_LE_CREATE_CONN = 0x000D
OCF_LE_SET_ADVERTISING_PARAMETERS = 0x0006
OCF_LE_SET_ADVERTISE_ENABLE = 0x000A
OCF_LE_SET_ADVERTISING_DATA = 0x0008

# Allow Scan Request from Any, Connect Request from Any
FILTER_POLICY_NO_ALLOWLIST = 0x00
# Allow Scan Request from White List Only, Connect Request from Any
FILTER_POLICY_SCAN_ALLOWLIST = 0x01
# Allow Scan Request from Any, Connect Request from White List Only
FILTER_POLICY_CONN_ALLOWLIST = 0x02
# Allow Scan Request from White List Only, Connect Request from White List Only
FILTER_POLICY_SCAN_AND_CONN_ALLOWLIST = 0x03


logger = logging.getLogger(__name__)


class Handler(Protocol):
    def __call__(self, mac: str, adv: int, data: bytes, rssi: int) -> None:
        ...


def raw_packet_to_str(pkt: bytes) -> str:
    return ''.join(f'{struct.unpack("B", bytes([x]))[0]:02x}' for x in pkt)


def disable_le_scan(sock: btsocket) -> None:
    """Disable LE scan."""
    cmd_pkt = struct.pack('<BB', SCAN_DISABLE, 0x00)
    hci_send_cmd(sock, OGF_LE_CTL, OCF_LE_SET_SCAN_ENABLE, cmd_pkt)


def enable_le_scan(
        sock: btsocket,
        interval: int = 0x0800,
        window: int = 0x0800,
        filter_policy: int = FILTER_POLICY_NO_ALLOWLIST,
        filter_duplicates: bool = False,
) -> None:
    """
    Enable LE passive scan (with filtering of duplicate packets enabled).

    :param interval: Scan interval.
    :param window: Scan window (must be less or equal than given interval).
    :param filter_policy: One of
        ``FILTER_POLICY_NO_ALLOWLIST`` (default value)
        ``FILTER_POLICY_SCAN_ALLOWLIST``
        ``FILTER_POLICY_CONN_ALLOWLIST``
        ``FILTER_POLICY_SCAN_AND_CONN_ALLOWLIST``

    .. note:: Scan interval and window are to multiply by 0.625 ms to
        get the real time duration.
    """
    if window > interval:
        raise ValueError('scan window must be less than or equal to interval')

    # N.B. does not work with LE_RANDOM_ADDRESS
    cmd_pkt = struct.pack(
        '<BHHBB', SCAN_TYPE_PASSIVE, interval, window, LE_PUBLIC_ADDRESS,
        filter_policy,
    )
    hci_send_cmd(sock, OGF_LE_CTL, OCF_LE_SET_SCAN_PARAMETERS, cmd_pkt)
    logger.debug(
        'enabling le scan',
        extra={
            'interval': f'{interval * 0.625:.3f}ms',
            'window': f'{window * 0.625:.3f}ms',
            'allowlist': filter_policy in (
                FILTER_POLICY_SCAN_ALLOWLIST,
                FILTER_POLICY_SCAN_AND_CONN_ALLOWLIST,
            ),
        },
    )
    scan_filter = SCAN_FILTER_DUPLICATES if filter_duplicates else 0x00
    cmd_pkt = struct.pack('<BB', SCAN_ENABLE, scan_filter)
    hci_send_cmd(sock, OGF_LE_CTL, OCF_LE_SET_SCAN_ENABLE, cmd_pkt)


def parse_le_advertising_events(
        sock: btsocket,
        handler: Handler,
        filter_mac_addrs: Optional[Sequence[str]] = None,
        filter_packet_length: Optional[int] = None,
) -> None:
    """
    Parse and report LE advertisements.

    This is a blocking call, an infinite loop is started and the given handler
    will be called each time a new LE advertisement packet is detected and
    corresponds to the given filters.
    """
    # pylint: disable=too-many-locals
    old_filter = sock.getsockopt(SOL_HCI, HCI_FILTER, 14)

    flt = hci_filter_new()
    hci_filter_set_ptype(flt, HCI_EVENT_PKT)
    hci_filter_set_event(flt, LE_META_EVENT)
    sock.setsockopt(SOL_HCI, HCI_FILTER, flt)

    try:
        logger.info(
            'socket filter set, listening for data',
            extra={'event': 'LE_META_EVENT', 'ptype': 'HCI_EVENT_PKT'},
        )

        while True:
            pkt = sock.recv(255)
            _ptype, event, plen = struct.unpack('BBB', pkt[:3])
            if event != LE_META_EVENT:
                # should never occur because we filtered to this type of event
                logger.error('received invalid event', extra={'event': event})
                continue

            sub_event, = struct.unpack('B', pkt[3:4])
            if sub_event != EVT_LE_ADVERTISING_REPORT:
                logger.debug('not an EVT_LE_ADVERTISING_REPORT')
                continue

            body = pkt[4:]
            adv_type = struct.unpack('b', body[1:2])[0]
            mac_addr = ba2str(body[3:9])
            log_context = {
                'adv_type': f'{adv_type:02x}',
                'mac': mac_addr,
                'plen': plen,
            }

            if filter_packet_length and plen != filter_packet_length:
                logger.debug(
                    'packet with non-matching length',
                    extra=log_context | {'data': raw_packet_to_str(body)},
                )
                continue

            data = body[9:-1]
            rssi = struct.unpack('b', pkt[len(pkt) - 1:len(pkt)])[0]
            log_context['rssi'] = rssi

            if filter_mac_addrs and mac_addr not in filter_mac_addrs:
                logger.debug(
                    'packet with non-matching mac',
                    extra=log_context | {'data': raw_packet_to_str(data)},
                )
                continue

            logger.debug(
                'LE advertisement',
                extra=log_context | {'data': raw_packet_to_str(data)},
            )

            try:
                handler(mac_addr, adv_type, data, rssi)
            except Exception:
                logger.exception('handler raised exception')
    finally:
        logger.debug('restoring previous socket filter')
        sock.setsockopt(SOL_HCI, HCI_FILTER, old_filter)


def toggle_device(interface: int, enable: bool) -> None:
    """Power ON or OFF a bluetooth device."""
    sock = socket.socket(AF_BLUETOOTH, socket.SOCK_RAW, BTPROTO_HCI)
    logger.info('toggling bluetooth device %d: %s', interface, enable)
    request = array.array('b', struct.pack('H', interface))
    try:
        fcntl.ioctl(
            sock.fileno(),
            HCIDEVUP if enable else HCIDEVDOWN,
            request[0],
        )
    except OSError as e:
        if e.errno != errno.EALREADY:
            raise
    finally:
        sock.close()
