import contextlib
import struct
from typing import Any
from typing import cast

from . import fields

HCI_COMMAND = 0x01
HCI_EVENT = 0x04


def decode_fields(seq: list[Any], data: bytes) -> bytes:
    # Decode a sequence of fields in order; the payload is dynamically typed so
    # the known-bytes result is asserted here rather than at each call site.
    for field in seq:
        data = field.decode(data)
    return cast('bytes', data)


class Packet:
    def __init__(self, header: int = 0, fmt: str = '>B') -> None:
        self.header = header
        self.fmt = fmt
        self.payload: list[Any] = []
        self.raw_data: bytes | None = None

    def encode(self) -> bytes:
        return struct.pack(self.fmt, self.header)

    def decode(self, data: bytes) -> bytes | None:
        size = struct.calcsize(self.fmt)
        with contextlib.suppress(Exception):
            if struct.unpack(self.fmt, data[:size])[0] == self.header:
                self.raw_data = data
                return data[size:]
        return None

    def retrieve(self, aclass: str | type) -> list[Any]:
        # Reflective lookup returning matching sub-fields by name or class; the
        # heterogeneous field payload is intentionally dynamically typed.
        resu = []
        for field in self.payload:
            with contextlib.suppress(Exception):
                if isinstance(aclass, str):
                    if field.name == aclass:
                        resu.append(field)
                elif isinstance(field, aclass):
                    resu.append(field)
                resu += field.retrieve(aclass)
        return resu


class HCI_Command(Packet):
    def __init__(self, ogf: bytes, ocf: bytes) -> None:
        super().__init__(HCI_COMMAND)
        self.cmd = fields.OgfOcf('command', ogf, ocf)
        self.payload = []

    def encode(self) -> bytes:
        pld = b''
        for field in self.payload:
            pld += field.encode()
        return b''.join(
            [
                super().encode(),
                self.cmd.encode(),
                struct.pack('>B', len(pld)),
                pld,
            ]
        )


class RepeatedField(Packet):
    def __init__(
        self,
        name: str,
        subfield_cls: type,
        length_field_cls: type | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.subfield_cls = subfield_cls
        length_cls = (
            fields.UIntByte if length_field_cls is None else length_field_cls
        )
        self.length_field = length_cls('count of ' + name)
        self.payload = []

    def decode(self, data: bytes) -> bytes:
        self.payload = []
        data = self.length_field.decode(data)
        for _ in range(self.length_field.val):
            field = self.subfield_cls()
            data = field.decode(data)
            self.payload.append(field)
        return cast('bytes', data)
