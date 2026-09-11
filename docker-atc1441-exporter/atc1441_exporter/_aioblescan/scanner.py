import asyncio
import platform
import socket
import struct
from collections.abc import Callable
from typing import cast

from . import base
from . import commands
from . import events
from . import fields


def create_bt_socket(interface: int = 0) -> socket.socket:
    if platform.system() != 'Linux':
        raise OSError('Platform not supported')

    # AF_BLUETOOTH/BTPROTO_HCI/SOL_HCI/HCI_FILTER exist only on Linux.
    # pylint: disable=no-member
    sock = socket.socket(
        family=socket.AF_BLUETOOTH,
        type=socket.SOCK_RAW,
        proto=socket.BTPROTO_HCI,
    )
    try:
        sock.setblocking(False)
        # type mask, event mask, event mask, opcode
        sock.setsockopt(
            socket.SOL_HCI,
            socket.HCI_FILTER,  # ty: ignore[unresolved-attribute]
            struct.pack('IIIh2x', 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0),
        )
        sock.bind((interface,))
    except OSError as exc:
        sock.close()
        msg = f'error binding on interface {interface!r}: {exc.strerror}'
        raise OSError(exc.errno, msg) from exc
    # pylint: enable=no-member
    return sock


class BLEScanRequester(asyncio.Protocol):
    """asyncio protocol driving an HCI socket to scan for adverts."""

    def __init__(self) -> None:
        self._supported_commands: bytes | None = None
        self._le_features: bytes | None = None
        self._initialized = asyncio.Event()
        self._uninitialized = True
        self.transport: asyncio.WriteTransport | None = None
        self.process: Callable[[bytes], None] = self.default_process

    def _use_ext_scan(self) -> bool:
        # Bluetooth Core Spec Vol 2, Part E, Section 6.27: use LE extended scan
        # when the extended set-scan commands are supported.
        assert self._supported_commands is not None
        return (self._supported_commands[37] & 0x60) == 0x60

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = cast('asyncio.WriteTransport', transport)
        self.transport.write(
            commands.HCI_Cmd_Read_Local_Supported_Commands().encode()
        )

    async def send_scan_request(self, isactivescan: bool = False) -> None:
        await self._initialized.wait()
        if self._use_ext_scan():
            sparam = [int(isactivescan)] * 8
            self._write(
                commands.HCI_Cmd_LE_Set_Extended_Scan_Params(scan_type=sparam)
            )
            self._write(commands.HCI_Cmd_LE_Set_Extended_Scan_Enable(True, 0))
        else:
            self._write(
                commands.HCI_Cmd_LE_Set_Scan_Params(
                    scan_type=int(isactivescan)
                )
            )
            self._write(commands.HCI_Cmd_LE_Scan_Enable(True, False))

    async def stop_scan_request(self) -> None:
        await self._initialized.wait()
        if self._use_ext_scan():
            self._write(commands.HCI_Cmd_LE_Set_Extended_Scan_Enable(False, 0))
        else:
            self._write(commands.HCI_Cmd_LE_Scan_Enable(False, False))

    async def send_command(self, command: base.HCI_Command) -> None:
        await self._initialized.wait()
        self._write(command)

    def _write(self, command: base.HCI_Command) -> None:
        assert self.transport is not None
        self.transport.write(command.encode())

    def data_received(self, data: bytes) -> None:
        if self._uninitialized:
            event = events.HCI_Event()
            event.decode(data)
            if event.payload[0].val == b'\x0e':
                cc = event.retrieve('Command Completed')[0]
                cmd = cc.retrieve(fields.OgfOcf)[0]
                opcode = (ord(cmd.ogf) << 10) | ord(cmd.ocf)
                resp = cc.retrieve('resp code')[0]
                if opcode == 0x1002:
                    self._handle_supported_commands(resp.val)
                elif opcode == 0x2003:
                    self._handle_le_features(resp.val)
                return
        self.process(data)

    def _handle_supported_commands(self, resp: bytes) -> None:
        self._supported_commands = resp[1:] if resp[0] == 0 else bytes(64)
        assert self.transport is not None
        self.transport.write(
            commands.HCI_Cmd_LE_Read_Local_Supported_Features().encode()
        )

    def _handle_le_features(self, resp: bytes) -> None:
        self._le_features = resp[1:] if resp[0] == 0 else bytes(8)
        self._initialized.set()
        self._uninitialized = False

    def default_process(self, data: bytes) -> None:
        pass
