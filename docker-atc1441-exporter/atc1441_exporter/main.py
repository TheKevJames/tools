import argparse
import asyncio
import configparser
import contextlib
import dataclasses
import logging
import os
import socket
import struct
from collections.abc import Callable
from typing import cast

import prometheus_client

from . import utils
from ._aioblescan import events
from ._aioblescan import scanner

# Environmental Sensing UUID 0x181A, as the vendored parser presents it (it
# reverses the little-endian wire bytes).
ATC1441_SERVICE_UUID = b'\x18\x1a'
# mac(6) temp(2, 0.1C) humidity(1, %) battery(1, %) battery(2, mV) counter(1)
ATC1441_PAYLOAD = struct.Struct('>6shBBHB')

DEBUG = os.environ.get('DEBUG', '').lower() == 'true'


logger = logging.getLogger('app.main')


@dataclasses.dataclass
class Measurement:
    battery: int
    humidity: int
    temperature: float
    voltage: float


class Metrics:
    def __init__(self, registry: prometheus_client.CollectorRegistry) -> None:
        self.battery = prometheus_client.Gauge(
            'atc_battery', 'Battery', ['name'], registry=registry
        )
        self.humidity = prometheus_client.Gauge(
            'atc_humidity', 'Humidity', ['name'], registry=registry
        )
        self.temperature = prometheus_client.Gauge(
            'atc_temperature', 'Temp.', ['name'], registry=registry
        )
        self.voltage = prometheus_client.Gauge(
            'atc_voltage', 'Voltage', ['name'], registry=registry
        )

    def record(self, name: str, measurement: Measurement) -> None:
        self.battery.labels(name).set(measurement.battery)
        self.humidity.labels(name).set(measurement.humidity)
        self.temperature.labels(name).set(measurement.temperature)
        self.voltage.labels(name).set(measurement.voltage)


def atc1441_service_data(event: events.HCI_Event) -> bytes | None:
    for adv in event.retrieve(events.Adv_Data):
        uuid, *payload = adv.payload
        if uuid.val == ATC1441_SERVICE_UUID and payload:
            return cast('bytes', payload[0].val)
    return None


def decode_data_atc1441(
    adv_cache: dict[str, int], mac: str, payload: bytes
) -> Measurement | None:
    if len(payload) != ATC1441_PAYLOAD.size:
        logger.debug('dropping packet with invalid length')
        return None

    _, temp, humidity, battery_percent, battery_mv, adv_number = (
        ATC1441_PAYLOAD.unpack(payload)
    )
    if adv_cache.get(mac) == adv_number:
        return None

    logger.info('received ATC1441 packet from %s', mac)
    adv_cache[mac] = adv_number

    return Measurement(
        battery=battery_percent,
        humidity=humidity,
        temperature=temp / 10.0,
        voltage=battery_mv / 1000,
    )


async def _open_scanner(
    loop: asyncio.AbstractEventLoop, sock: socket.socket
) -> tuple[asyncio.BaseTransport, scanner.BLEScanRequester]:
    # asyncio's public loop.create_connection rejects the SOCK_RAW HCI
    # socket, so we use the private _create_connection_transport that
    # aioblescan relies on. Isolated here (via getattr) so a future CPython
    # change is a one-line fix.
    create_transport = getattr(loop, '_create_connection_transport')
    transport, protocol = await create_transport(
        sock, scanner.BLEScanRequester, None, None
    )
    return (
        cast('asyncio.BaseTransport', transport),
        cast('scanner.BLEScanRequester', protocol),
    )


def build_processor(
    sensors: configparser.ConfigParser,
    registry: prometheus_client.CollectorRegistry = prometheus_client.REGISTRY,
) -> Callable[[bytes], None]:
    metrics = Metrics(registry)
    adv_cache: dict[str, int] = {}

    # The vendored parser emits lowercase MACs, so normalise the configured
    # section names to match regardless of how the user cased config.ini.
    names_by_mac = {
        section.lower(): sensors[section]['name']
        for section in sensors.sections()
    }

    def process(data: bytes) -> None:
        event = events.HCI_Event()
        try:
            event.decode(data)
        except Exception:
            logger.exception('could not decode HCI event')
            return

        peers = event.retrieve('peer')
        if not peers:
            return
        mac = peers[0].val
        name = names_by_mac.get(mac)
        if name is None:
            logger.debug('dropping packet for untracked device: %s', mac)
            return

        payload = atc1441_service_data(event)
        if payload is None:
            logger.debug('dropping packet without ATC1441 service data')
            return

        measurement = decode_data_atc1441(adv_cache, mac, payload)
        if not measurement:
            return

        metrics.record(name, measurement)

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
        sock = scanner.create_bt_socket(interface)
    except Exception:
        logger.exception('could not open bluetooth device %i', interface)
        raise

    loop = asyncio.get_running_loop()
    transport, btctrl = await _open_scanner(loop, sock)
    btctrl.process = build_processor(sensors)

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
