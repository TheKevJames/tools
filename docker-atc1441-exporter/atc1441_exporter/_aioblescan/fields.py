import struct

# Primitive wire-format fields. Each field exposes ``decode(data)`` and, where
# it is emitted as part of an HCI command, ``encode()``.


class MACAddr:
    def __init__(self, name: str, mac: str = '00:00:00:00:00:00') -> None:
        self.name = name
        self.val = mac.lower()

    def decode(self, data: bytes) -> bytes:
        self.val = ':'.join(f'{x:02x}' for x in reversed(data[:6]))
        return data[6:]

    def __len__(self) -> int:
        return 6


class Bool:
    def __init__(self, name: str, val: bool = True) -> None:
        self.name = name
        self.val = val

    def encode(self) -> bytes:
        return b'\x01' if self.val else b'\x00'

    def decode(self, data: bytes) -> bytes:
        self.val = data[:1] == b'\x01'
        return data[1:]

    def __len__(self) -> int:
        return 1


class Byte:
    def __init__(self, name: str, val: bytes = b'\0') -> None:
        self.name = name
        self.val = val

    def decode(self, data: bytes) -> bytes:
        self.val = struct.unpack('<c', data[:1])[0]
        return data[1:]

    def __len__(self) -> int:
        return 1


class EnumByte:
    def __init__(self, name: str, val: int, loval: dict[int, str]) -> None:
        self.name = name
        self.val = val
        self.loval = loval

    def encode(self) -> bytes:
        return struct.pack('>B', self.val)

    def decode(self, data: bytes) -> bytes:
        self.val = struct.unpack('>B', data[:1])[0]
        return data[1:]

    @property
    def strval(self) -> str:
        return self.loval.get(self.val, str(self.val))

    def __len__(self) -> int:
        return 1


class BitFieldByte:
    def __init__(self, name: str, val: int, loval: list[str]) -> None:
        self.name = name
        self._val = val
        self.loval = loval

    def encode(self) -> bytes:
        return struct.pack('>B', self._val)

    def decode(self, data: bytes) -> bytes:
        self._val = struct.unpack('>B', data[:1])[0]
        return data[1:]

    @property
    def val(self) -> dict[str, bool]:
        resu = {}
        mybit = 1 << (len(self.loval) - 1)
        for name in self.loval:
            if name not in ('Undef', 'Reserv'):
                resu[name] = (self._val & mybit) > 0
            mybit >>= 1
        return resu

    def __len__(self) -> int:
        return 1


class IntByte:
    def __init__(self, name: str, val: int = 0) -> None:
        self.name = name
        self.val = val

    def decode(self, data: bytes) -> bytes:
        self.val = struct.unpack('>b', data[:1])[0]
        return data[1:]

    def __len__(self) -> int:
        return 1


class UIntByte:
    def __init__(self, name: str, val: int = 0) -> None:
        self.name = name
        self.val = val

    def decode(self, data: bytes) -> bytes:
        self.val = struct.unpack('>B', data[:1])[0]
        return data[1:]

    def __len__(self) -> int:
        return 1


class UShortInt:
    def __init__(self, name: str, val: int = 0, endian: str = 'big') -> None:
        self.name = name
        self.val = val
        self.endian = endian

    def encode(self) -> bytes:
        return struct.pack('>H' if self.endian == 'big' else '<H', self.val)

    def decode(self, data: bytes) -> bytes:
        fmt = '>H' if self.endian == 'big' else '<H'
        self.val = struct.unpack(fmt, data[:2])[0]
        return data[2:]

    def __len__(self) -> int:
        return 2


class OgfOcf:
    def __init__(
        self, name: str, ogf: bytes = b'\x00', ocf: bytes = b'\x00'
    ) -> None:
        self.name = name
        self.ogf = ogf
        self.ocf = ocf

    def encode(self) -> bytes:
        return struct.pack('<H', (ord(self.ogf) << 10) | ord(self.ocf))

    def decode(self, data: bytes) -> bytes:
        val = struct.unpack('<H', data[: len(self)])[0]
        ogf = val >> 10
        self.ocf = int(val - (ogf << 10)).to_bytes(1, 'big')
        self.ogf = int(ogf).to_bytes(1, 'big')
        return data[len(self) :]

    def __len__(self) -> int:
        return struct.calcsize('<H')


class Itself:
    def __init__(self, name: str) -> None:
        self.name = name
        self.val = b''

    def decode(self, data: bytes) -> bytes:
        self.val = struct.unpack(f'>{len(data)}s', data)[0]
        return b''

    def __len__(self) -> int:
        return len(self.val)


class String:
    def __init__(self, name: str) -> None:
        self.name = name
        self.val: bytes = b''

    def decode(self, data: bytes) -> bytes:
        self.val = data
        return b''

    def __len__(self) -> int:
        return len(self.val)


class NBytes:
    def __init__(self, name: str, length: int = 2) -> None:
        self.name = name
        self.length = length
        self.val = b''

    def decode(self, data: bytes) -> bytes:
        self.val = struct.unpack(f'>{self.length}s', data[: self.length])[0][
            ::-1
        ]
        return data[self.length :]

    def __len__(self) -> int:
        return self.length


class NBytes_List:
    def __init__(self, name: str, nbytes: int = 2) -> None:
        self.name = name
        self.length = nbytes
        self.lonbytes: list[NBytes] = []

    def decode(self, data: bytes) -> bytes:
        while data:
            mynbyte = NBytes('', self.length)
            data = mynbyte.decode(data)
            self.lonbytes.append(mynbyte)
        return data

    def __len__(self) -> int:
        return len(self.lonbytes) + self.length
