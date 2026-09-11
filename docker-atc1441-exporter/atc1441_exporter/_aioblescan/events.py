from collections.abc import Callable
from typing import Any

from . import base
from . import fields


class EIR_Hdr(base.Packet):
    _TYPES = {
        0x01: 'flags',
        0x02: 'incomplete_list_16_bit_svc_uuids',
        0x03: 'complete_list_16_bit_svc_uuids',
        0x04: 'incomplete_list_32_bit_svc_uuids',
        0x05: 'complete_list_32_bit_svc_uuids',
        0x06: 'incomplete_list_128_bit_svc_uuids',
        0x07: 'complete_list_128_bit_svc_uuids',
        0x08: 'shortened_local_name',
        0x09: 'complete_local_name',
        0x0A: 'tx_power_level',
        0x0D: 'class_of_device',
        0x0E: 'simple_pairing_hash',
        0x0F: 'simple_pairing_rand',
        0x10: 'sec_mgr_tk',
        0x11: 'sec_mgr_oob_flags',
        0x12: 'slave_conn_intvl_range',
        0x17: 'pub_target_addr',
        0x18: 'rand_target_addr',
        0x19: 'appearance',
        0x1A: 'adv_intvl',
        0x1B: 'le_addr',
        0x1C: 'le_role',
        0x14: 'list_16_bit_svc_sollication_uuids',
        0x1F: 'list_32_bit_svc_sollication_uuids',
        0x15: 'list_128_bit_svc_sollication_uuids',
        0x16: 'svc_data_16_bit_uuid',
        0x20: 'svc_data_32_bit_uuid',
        0x21: 'svc_data_128_bit_uuid',
        0x22: 'sec_conn_confirm',
        0x23: 'sec_conn_rand',
        0x24: 'uri',
        0xFF: 'mfg_specific_data',
    }

    def __init__(self) -> None:
        super().__init__()
        self.type = fields.EnumByte('type', 0, self._TYPES)

    def decode(self, data: bytes) -> bytes:
        return self.type.decode(data)

    @property
    def val(self) -> int:
        return self.type.val

    @property
    def strval(self) -> str:
        return self.type.strval

    def __len__(self) -> int:
        return len(self.type)


class Adv_Data(base.Packet):
    def __init__(self, name: str, length: int) -> None:
        super().__init__()
        self.name = name
        self.length = length
        self.payload = []

    def decode(self, data: bytes) -> bytes:
        uuid = fields.NBytes('Service Data uuid', self.length)
        data = uuid.decode(data)
        self.payload.append(uuid)
        if data:
            payload = fields.Itself('Adv Payload')
            data = payload.decode(data)
            self.payload.append(payload)
        return data

    def __len__(self) -> int:
        return sum(len(x) for x in self.payload)


class ManufacturerSpecificData(base.Packet):
    def __init__(self, name: str = 'Manufacturer Specific Data') -> None:
        super().__init__()
        self.name = name
        self.payload = [
            fields.UShortInt('Manufacturer ID', endian='little'),
            fields.Itself('Payload'),
        ]

    def decode(self, data: bytes) -> bytes:
        return base.decode_fields(self.payload, data)


_FLAG_NAMES = [
    'Undef',
    'Undef',
    'Simul LE - BR/EDR (Host)',
    'Simul LE - BR/EDR (Control.)',
    'BR/EDR Not Supported',
    'LE General Disc.',
    'LE Limited Disc.',
]

# Factory table mapping an EIR/AD type byte to the field decoding its value.
# A dict dispatch keeps AD_Structure.decode free of a long if/elif chain.
_AD_VALUE_FACTORIES: dict[int, Callable[[], Any]] = {
    0x01: lambda: fields.BitFieldByte('flags', 0, _FLAG_NAMES),
    0x02: lambda: fields.NBytes_List('Incomplete uuids', 2),
    0x03: lambda: fields.NBytes_List('Complete uuids', 2),
    0x04: lambda: fields.NBytes_List('Incomplete uuids', 4),
    0x05: lambda: fields.NBytes_List('Complete uuids', 4),
    0x06: lambda: fields.NBytes_List('Incomplete uuids', 16),
    0x07: lambda: fields.NBytes_List('Complete uuids', 16),
    0x08: lambda: fields.String('Short Name'),
    0x09: lambda: fields.String('Complete Name'),
    0x14: lambda: fields.NBytes_List('Service Solicitation uuid', 2),
    0x15: lambda: fields.NBytes_List('Service Solicitation uuid', 16),
    0x16: lambda: Adv_Data('Advertised Data', 2),
    0x1F: lambda: fields.NBytes_List('Service Solicitation uuid', 4),
    0x20: lambda: Adv_Data('Advertised Data', 4),
    0x21: lambda: Adv_Data('Advertised Data', 16),
    0xFF: ManufacturerSpecificData,
}


class AD_Structure(base.Packet):
    def __init__(self) -> None:
        super().__init__()
        self.name = ''
        self.length = 0
        self.payload = []

    def decode(self, data: bytes) -> bytes:
        sublen = fields.UIntByte('sublen')
        data = sublen.decode(data)
        self.length = len(sublen) + sublen.val
        self.payload = []
        if sublen.val == 0:
            return data

        hdr = EIR_Hdr()
        data = hdr.decode(data)
        factory = _AD_VALUE_FACTORIES.get(hdr.val)
        val = (
            factory()
            if factory
            else fields.Itself(f'Payload for {hdr.strval}')
        )

        # Some value types consume all input, so pass only this structure.
        val.decode(data[: sublen.val - len(hdr)])
        self.payload.extend((hdr, val))
        return data[sublen.val - len(hdr) :]

    def __len__(self) -> int:
        return self.length


class HCI_LEM_Adv_Report(base.Packet):
    def __init__(self) -> None:
        super().__init__()
        self.name = 'Adv Report'
        self.payload = [
            fields.EnumByte(
                'ev type',
                0,
                {0: 'generic adv', 3: 'no connection adv', 4: 'scan rsp'},
            ),
            fields.EnumByte('addr type', 0, {0: 'public', 1: 'random'}),
            fields.MACAddr('peer'),
            fields.UIntByte('length'),
        ]

    def decode(self, data: bytes) -> bytes:
        data = base.decode_fields(self.payload, data)
        packet_len = self.payload[3].val
        while packet_len > 0:
            ad = AD_Structure()
            data = ad.decode(data)
            self.payload.append(ad)
            packet_len -= ad.length
            if ad.length == 0:  # sanity check to avoid an infinite loop
                packet_len = 0
        if data:
            rssi = fields.IntByte('rssi')
            data = rssi.decode(data)
            self.payload.append(rssi)
        return data


class HCI_LEM_Ext_Adv_Report(base.Packet):
    def __init__(self) -> None:
        super().__init__()
        self.name = 'Ext Adv Report'
        self.payload = [
            fields.BitFieldByte(
                'ev type',
                0,
                [
                    'Connectable',
                    'Scannable',
                    'Directed',
                    'Scan Response',
                    'Legacy',
                    'Incomplete/more',
                    'Incomplete/truncated',
                    'RFU',
                ],
            ),
            fields.UIntByte('unused'),
            fields.EnumByte(
                'addr type',
                0,
                {
                    0: 'public device',
                    1: 'random device',
                    2: 'public identity',
                    3: 'random identity',
                    0xFF: 'anonymous',
                },
            ),
            fields.MACAddr('peer'),
            fields.EnumByte('primary phy', 1, {1: 'LE 1M', 3: 'LE Coded'}),
            fields.EnumByte(
                'secondary phy',
                0,
                {0: 'N/A', 1: 'LE 1M', 2: 'LE 2M', 3: 'LE Coded'},
            ),
            fields.EnumByte(
                'adv sid',
                255,
                {i: f'0x{i:02X}' for i in range(16)} | {0xFF: 'N/A'},
            ),
            fields.IntByte('tx power'),
            fields.IntByte('rssi'),
            fields.UShortInt('adv interval', endian='little'),
            fields.EnumByte(
                'direct addr type',
                0,
                {
                    0: 'public device',
                    1: 'random device',
                    2: 'public identity',
                    3: 'random identity',
                    0xFE: 'random device',
                },
            ),
            fields.MACAddr('direct addr'),
            fields.UIntByte('data len'),
        ]

    def decode(self, data: bytes) -> bytes:
        data = base.decode_fields(self.payload, data)
        datalength = self.payload[-1].val
        while datalength > 0:
            ad = AD_Structure()
            data = ad.decode(data)
            self.payload.append(ad)
            datalength -= len(ad)
        return data


class HCI_LE_Meta_Event(base.Packet):
    def __init__(self) -> None:
        super().__init__()
        self.name = 'LE Meta'
        self.payload = [fields.Byte('code')]

    def decode(self, data: bytes) -> bytes:
        data = base.decode_fields(self.payload, data)
        code = self.payload[0]
        if code.val == b'\x02':
            ev = base.RepeatedField('Adv Report', HCI_LEM_Adv_Report)
        elif code.val == b'\x0d':
            ev = base.RepeatedField('Ext Adv Report', HCI_LEM_Ext_Adv_Report)
        else:
            ev = fields.Itself('Payload')
        data = ev.decode(data)
        self.payload.append(ev)
        return data


class HCI_CC_Event(base.Packet):
    def __init__(self) -> None:
        super().__init__()
        self.name = 'Command Completed'
        self.payload = [
            fields.UIntByte('allow pkt'),
            fields.OgfOcf('cmd'),
            fields.Itself('resp code'),
        ]

    def decode(self, data: bytes) -> bytes:
        return base.decode_fields(self.payload, data)


class HCI_Event(base.Packet):
    def __init__(self) -> None:
        super().__init__(base.HCI_EVENT)
        self.payload = [fields.Byte('code'), fields.UIntByte('length')]

    def decode(self, data: bytes) -> bytes | None:
        remaining = super().decode(data)
        if remaining is None:
            return None
        data = remaining

        for field in self.payload:
            field.decode(data[: len(field)])
            data = data[len(field) :]

        code = self.payload[0]
        if code.val == b'\x0e':
            ev = HCI_CC_Event()
        elif code.val == b'\x3e':
            ev = HCI_LE_Meta_Event()
        else:
            ev = fields.Itself('Payload')
        data = ev.decode(data)
        self.payload.append(ev)
        return data
