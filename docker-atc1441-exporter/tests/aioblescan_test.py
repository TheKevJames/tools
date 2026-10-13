import asyncio
import struct
from typing import cast

import hypothesis
import hypothesis.strategies

from atc1441_exporter._aioblescan import commands
from atc1441_exporter._aioblescan import fields
from atc1441_exporter._aioblescan import scanner

_bytes = hypothesis.strategies.integers(0, 255)


@hypothesis.given(val=hypothesis.strategies.booleans(), rest=_bytes)
def test_bool_round_trips(val: bool, rest: int) -> None:
    decoded = fields.Bool('x', not val)
    assert decoded.decode(fields.Bool('x', val).encode() + bytes([rest])) == (
        bytes([rest])
    )
    assert decoded.val is val


@hypothesis.given(val=_bytes)
def test_enum_byte_round_trips(val: int) -> None:
    decoded = fields.EnumByte('x', 0, {})
    assert decoded.decode(fields.EnumByte('x', val, {}).encode()) == b''
    assert decoded.val == val


@hypothesis.given(data=hypothesis.strategies.binary(min_size=1))
def test_bit_field_byte_round_trips(data: bytes) -> None:
    # The raw byte is private; only re-encoding exposes it.
    field = fields.BitFieldByte('x', 0, ['a'] * 8)
    assert field.decode(data) == data[1:]
    assert field.encode() == data[:1]


@hypothesis.given(
    val=hypothesis.strategies.integers(0, 2**16 - 1),
    endian=hypothesis.strategies.sampled_from(['big', 'little']),
)
def test_ushort_int_round_trips(val: int, endian: str) -> None:
    decoded = fields.UShortInt('x', endian=endian)
    assert decoded.decode(fields.UShortInt('x', val, endian).encode()) == b''
    assert decoded.val == val


# OCF is 10 bits on the wire but OgfOcf stores it as a single byte.
@hypothesis.given(ogf=hypothesis.strategies.integers(0, 63), ocf=_bytes)
def test_ogf_ocf_round_trips(ogf: int, ocf: int) -> None:
    encoded = fields.OgfOcf('x', bytes([ogf]), bytes([ocf])).encode()
    assert encoded == struct.pack('<H', ogf << 10 | ocf)

    decoded = fields.OgfOcf('x')
    assert decoded.decode(encoded) == b''
    assert (decoded.ogf, decoded.ocf) == (bytes([ogf]), bytes([ocf]))


def scan_param_slots(interval: float, window: float) -> tuple[int, int]:
    encoded = commands.HCI_Cmd_LE_Set_Scan_Params(
        interval=interval, window=window
    ).encode()
    return struct.unpack('<HH', encoded[5:9])


_millis = hypothesis.strategies.floats(
    -1e6, 1e6, allow_nan=False, allow_infinity=False
)


@hypothesis.given(interval=_millis, window=_millis)
def test_scan_params_clamp_to_valid_range(
    interval: float, window: float
) -> None:
    interval_slots, window_slots = scan_param_slots(interval, window)
    # Core Spec Vol 4, Part E, 7.8.10: 0x0004..0x4000 slots of 0.625 ms,
    # with the window no larger than the interval.
    assert 0x0004 <= window_slots <= interval_slots <= 0x4000


@hypothesis.given(slots=hypothesis.strategies.integers(0x0004, 0x4000))
def test_scan_params_encode_in_range_values_exactly(slots: int) -> None:
    assert scan_param_slots(slots * 0.625, slots * 0.625) == (slots, slots)


class FakeTransport:
    def __init__(self) -> None:
        self.written: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.written.append(data)


def command_complete(opcode: int, status: int, params: bytes) -> bytes:
    body = struct.pack('<BHB', 1, opcode, status) + params
    return bytes([0x04, 0x0E, len(body)]) + body


async def handshake(
    supported_commands: bytes,
) -> tuple[scanner.BLEScanRequester, FakeTransport, list[bytes]]:
    transport = FakeTransport()
    processed: list[bytes] = []
    requester = scanner.BLEScanRequester()
    requester.process = processed.append

    requester.connection_made(cast('asyncio.BaseTransport', transport))
    assert transport.written == [bytes.fromhex('01021000')]
    requester.data_received(command_complete(0x1002, 0, supported_commands))
    assert transport.written[1:] == [bytes.fromhex('01032000')]
    requester.data_received(command_complete(0x2003, 0, bytes(8)))
    transport.written.clear()
    return requester, transport, processed


EXT_SCAN_SUPPORTED = bytes(37) + b'\x60' + bytes(26)


def test_scanner_uses_legacy_scan_when_extended_unsupported() -> None:
    async def run() -> list[bytes]:
        requester, transport, _ = await handshake(bytes(64))
        await requester.send_scan_request()
        await requester.stop_scan_request()
        return transport.written

    assert asyncio.run(run()) == [
        bytes.fromhex('010b200700100010000000'),
        bytes.fromhex('010c20020100'),
        bytes.fromhex('010c20020000'),
    ]


def test_scanner_uses_extended_scan_when_supported() -> None:
    async def run() -> list[bytes]:
        requester, transport, _ = await handshake(EXT_SCAN_SUPPORTED)
        await requester.send_scan_request()
        await requester.stop_scan_request()
        return transport.written

    assert asyncio.run(run()) == [
        bytes.fromhex('014120080000010010001000'),
        bytes.fromhex('01422006010000000000'),
        bytes.fromhex('01422006000000000000'),
    ]


def test_scanner_treats_failed_command_query_as_unsupported() -> None:
    async def run() -> list[bytes]:
        transport = FakeTransport()
        requester = scanner.BLEScanRequester()
        requester.connection_made(cast('asyncio.BaseTransport', transport))
        requester.data_received(
            command_complete(0x1002, 0x01, EXT_SCAN_SUPPORTED)
        )
        requester.data_received(command_complete(0x2003, 0, bytes(8)))
        transport.written.clear()
        await requester.send_scan_request()
        return transport.written

    assert asyncio.run(run())[0] == bytes.fromhex('010b200700100010000000')


def test_scanner_forwards_events_after_handshake() -> None:
    advert = bytes.fromhex('043e0c02010000a4c138d8f89d00c5')

    async def run() -> list[bytes]:
        requester, _, processed = await handshake(bytes(64))
        requester.data_received(advert)
        return processed

    assert asyncio.run(run()) == [advert]
