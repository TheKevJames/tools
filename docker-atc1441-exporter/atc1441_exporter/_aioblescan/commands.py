from . import base
from . import fields

_OWN_ADDR_TYPES = {
    0: 'Public',
    1: 'Random',
    2: 'Private IRK or Public',
    3: 'Private IRK or Random',
}
_FILTER_POLICIES = {
    0: 'None',
    1: 'Sender In White List',
    2: 'Almost None',
    3: 'SIWL and some',
}
_SCAN_TYPES = {0: 'Passive', 1: 'Active'}


def _scan_interval(interval: float) -> int:
    return int(round(min(10240, max(2.5, interval)) / 0.625))


class HCI_Cmd_Read_Local_Supported_Commands(base.HCI_Command):
    def __init__(self) -> None:
        super().__init__(b'\x04', b'\x02')


class HCI_Cmd_LE_Read_Local_Supported_Features(base.HCI_Command):
    def __init__(self) -> None:
        super().__init__(b'\x08', b'\x03')


class HCI_Cmd_LE_Scan_Enable(base.HCI_Command):
    def __init__(self, enable: bool = True, filter_dups: bool = True) -> None:
        super().__init__(b'\x08', b'\x0c')
        self.payload.extend(
            (fields.Bool('enable', enable), fields.Bool('filter', filter_dups))
        )


class HCI_Cmd_LE_Set_Scan_Params(base.HCI_Command):
    def __init__(
        self,
        scan_type: int = 0x0,
        interval: float = 10,
        window: float = 750,
        oaddr_type: int = 0,
        nfilter: int = 0,
    ) -> None:
        super().__init__(b'\x08', b'\x0b')
        self.payload.extend(
            (
                fields.EnumByte('scan type', scan_type, _SCAN_TYPES),
                fields.UShortInt(
                    'Interval', _scan_interval(interval), endian='little'
                ),
                fields.UShortInt(
                    'Window',
                    _scan_interval(min(interval, window)),
                    endian='little',
                ),
                fields.EnumByte(
                    'own addresss type', oaddr_type, _OWN_ADDR_TYPES
                ),
                fields.EnumByte('filter policy', nfilter, _FILTER_POLICIES),
            )
        )


class HCI_Cmd_LE_Set_Extended_Scan_Enable(base.HCI_Command):
    def __init__(
        self,
        enable: bool = True,
        filter_dups: int = 1,
        duration: int = 0,
        period: int = 0,
    ) -> None:
        super().__init__(b'\x08', b'\x42')
        self.payload.extend(
            (
                fields.Bool('enable', enable),
                fields.EnumByte(
                    'filter',
                    filter_dups,
                    {0: 'Disable', 1: 'Enable', 2: 'Eanble with reset'},
                ),
                fields.UShortInt(
                    'Duration',
                    int(round(min(0xFFFF * 10, duration) / 10)),
                    endian='little',
                ),
                fields.UShortInt(
                    'Period',
                    int(
                        round(min(0xFFFF * 1280, max(period, duration)) / 1280)
                    ),
                    endian='little',
                ),
            )
        )


class HCI_Cmd_LE_Set_Extended_Scan_Params(base.HCI_Command):
    def __init__(
        self,
        oaddr_type: int = 0,
        nfilter: int = 0,
        phys: int = 1,
        scan_type: list[int] | None = None,
        interval: list[float] | None = None,
        window: list[float] | None = None,
    ) -> None:
        super().__init__(b'\x08', b'\x41')
        scan_type = [0] * 8 if scan_type is None else scan_type
        interval = [10] * 8 if interval is None else interval
        window = [750] * 8 if window is None else window
        self.payload.extend(
            (
                fields.EnumByte(
                    'own addresss type', oaddr_type, _OWN_ADDR_TYPES
                ),
                fields.EnumByte('filter policy', nfilter, _FILTER_POLICIES),
                fields.BitFieldByte(
                    'PHYs',
                    phys,
                    ['LE 1M', 'Reserv', 'LE Coded'] + ['Reserv'] * 5,
                ),
            )
        )

        mask = 0x01
        for i in range(8):
            if phys & mask:
                self.payload.extend(
                    (
                        fields.EnumByte(
                            'scan type', scan_type[i], _SCAN_TYPES
                        ),
                        fields.UShortInt(
                            'Interval',
                            _scan_interval(interval[i]),
                            endian='little',
                        ),
                        fields.UShortInt(
                            'Window',
                            _scan_interval(min(interval[i], window[i])),
                            endian='little',
                        ),
                    )
                )
            mask <<= 1
