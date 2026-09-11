import argparse
import asyncio
import configparser
import contextlib
import dataclasses
import logging
import os
import socket
from collections.abc import Callable
from typing import cast

import prometheus_client

from . import _aioblescan as aiobs
from . import utils

BATTERY = prometheus_client.Gauge('atc_battery', 'Battery', ['name'])
HUMIDITY = prometheus_client.Gauge('atc_humidity', 'Humidity', ['name'])
TEMPERATURE = prometheus_client.Gauge('atc_temperature', 'Temp.', ['name'])
VOLTAGE = prometheus_client.Gauge('atc_voltage', 'Voltage', ['name'])

# ATC1441 service data marker: AD type 0x16 (service data, 16-bit UUID)
# followed by UUID 0x181A on the wire (little-endian bytes 1a 18).
ATC_PREAMBLE = '161a18'

DEBUG = os.environ.get('DEBUG', '').lower() == 'true'


logger = logging.getLogger('app.main')


@dataclasses.dataclass
class Measurement:
    battery: int
    humidity: int
    temperature: float
    voltage: float


def decode_data_atc1441(
    adv_cache: dict[str, str], mac: str, data_str: str
) -> Measurement | None:
    data_idx = data_str.find(ATC_PREAMBLE)
    if data_idx == -1:
        logger.debug('dropping packet with missing preamble')
        return None

    offset = data_idx + len(ATC_PREAMBLE)
    stripped_data_str = data_str[offset : offset + 26]
    if len(stripped_data_str) != 26:
        logger.debug('dropping packet with invalid length')
        return None

    adv_number = stripped_data_str[-2:]  # last data in packet is adv number
    prev_adv_number = adv_cache.get(mac)
    if prev_adv_number == adv_number:
        return None

    logger.info('received ATC1441 packet from %s', mac)
    adv_cache[mac] = adv_number

    temp_bytes = bytearray.fromhex(stripped_data_str[12:16])
    temp = int.from_bytes(temp_bytes, byteorder='big', signed=True)
    humidity = int(stripped_data_str[16:18], 16)
    battery_voltage = int(stripped_data_str[20:24], 16) / 1000
    battery_percent = int(stripped_data_str[18:20], 16)

    return Measurement(
        battery=battery_percent,
        humidity=humidity,
        temperature=temp / 10.0,
        voltage=battery_voltage,
    )


async def _open_scanner(
    loop: asyncio.AbstractEventLoop, sock: socket.socket
) -> tuple[asyncio.BaseTransport, aiobs.BLEScanRequester]:
    # asyncio's public loop.create_connection rejects the SOCK_RAW HCI
    # socket, so we use the private _create_connection_transport that
    # aioblescan relies on. Isolated here (via getattr) so a future CPython
    # change is a one-line fix.
    create_transport = getattr(loop, '_create_connection_transport')
    transport, protocol = await create_transport(
        sock, aiobs.BLEScanRequester, None, None
    )
    return (
        cast('asyncio.BaseTransport', transport),
        cast('aiobs.BLEScanRequester', protocol),
    )


def _build_processor(
    sensors: configparser.ConfigParser,
) -> Callable[[bytes], None]:
    adv_cache: dict[str, str] = {}

    def process(data: bytes) -> None:
        event = aiobs.HCI_Event()
        try:
            event.decode(data)
        except Exception:
            logger.exception('could not decode HCI event')
            return

        if event.raw_data is None:
            return

        peers = event.retrieve('peer')
        if not peers:
            return
        mac = peers[0].val
        if mac not in sensors:
            return

        measurement = decode_data_atc1441(adv_cache, mac, event.raw_data.hex())
        if not measurement:
            return

        name = sensors[mac]['name']
        BATTERY.labels(name).set(measurement.battery)
        HUMIDITY.labels(name).set(measurement.humidity)
        TEMPERATURE.labels(name).set(measurement.temperature)
        VOLTAGE.labels(name).set(measurement.voltage)

    return process


async def _run(interface: int, port: int, filename: str) -> None:
    try:
        sensors = configparser.ConfigParser()
        sensors.read(filename)
    except Exception:
        logger.exception('could not parse device list file')
        raise

    utils.toggle_device(interface, True)

    try:
        sock = aiobs.create_bt_socket(interface)
    except Exception:
        logger.exception('could not open bluetooth device %i', interface)
        raise

    loop = asyncio.get_running_loop()
    transport, btctrl = await _open_scanner(loop, sock)
    # process is a callback slot on BLEScanRequester (defaults to a no-op);
    # override it with our advertisement handler.
    setattr(btctrl, 'process', _build_processor(sensors))

    prometheus_client.start_http_server(port)

    await btctrl.send_scan_request()
    try:
        await asyncio.Event().wait()  # scan until cancelled
    finally:
        await btctrl.stop_scan_request()
        transport.close()


def main() -> None:
    logging.basicConfig(
        format='[%(levelname)s] %(name)s\t%(message)s',
        level=logging.DEBUG if DEBUG else logging.INFO,
    )
    logger.info('starting atc1441-exporter')

    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument(
        '--interface',
        '-i',
        help='Specify the interface number to use, e.g. 1 for hci1',
        type=int,
        default=0,
    )
    parser.add_argument(
        '--port', '-p', help='OpenMetrics listen port', type=int, default=8000
    )
    parser.add_argument('filename', help='Specify a device list file')
    args = parser.parse_args()

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_run(args.interface, args.port, args.filename))


if __name__ == '__main__':
    main()
