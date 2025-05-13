import argparse
import configparser
import dataclasses
import logging
import os
import signal
from typing import Optional

import bluetooth._bluetooth as bluez
import prometheus_client

from .utils import disable_le_scan
from .utils import enable_le_scan
from .utils import parse_le_advertising_events
from .utils import raw_packet_to_str
from .utils import toggle_device


BATTERY = prometheus_client.Gauge('atc_battery', 'Battery', ['name'])
HUMIDITY = prometheus_client.Gauge('atc_humidity', 'Humidity', ['name'])
TEMPERATURE = prometheus_client.Gauge('atc_temperature', 'Temp.', ['name'])
VOLTAGE = prometheus_client.Gauge('atc_voltage', 'Voltage', ['name'])

DEBUG = os.environ.get('DEBUG', '').lower() == 'true'


logger = logging.getLogger('app.main')


@dataclasses.dataclass
class Measurement:
    battery: int
    humidity: int
    temperature: float
    voltage: float


def decode_data_atc1441(
        adv_cache: dict[str, str],
        mac: str,
        data_str: str,
) -> Optional[Measurement]:
    preamble = '161a18'
    data_idx = data_str.find(preamble)
    if data_idx == -1:
        logger.debug('dropping packet with missing preamble')
        return None

    offset = data_idx + len(preamble)
    stripped_data_str = data_str[offset:]
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
    batteryVoltage = int(stripped_data_str[20:24], 16) / 1000
    batteryPercent = int(stripped_data_str[18:20], 16)

    return Measurement(
        battery=batteryPercent,
        humidity=humidity,
        temperature=temp / 10.,
        voltage=batteryVoltage,
    )


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
        '--port',
        '-p',
        help='OpenMetrics listen port',
        type=int,
        default=8000,
    )
    parser.add_argument('filename', help='Specify a device list file')
    args = parser.parse_args()

    try:
        sensors = configparser.ConfigParser()
        sensors.read(args.filename)
    except Exception:
        logger.exception('could not parse device list file')
        raise

    toggle_device(args.interface, True)

    try:
        sock = bluez.hci_open_dev(args.interface)
    except Exception:
        logger.exception('could not open bluetooth device %i', args.interface)
        raise

    signal.signal(signal.SIGINT, lambda _sig, _frame: disable_le_scan(sock))
    enable_le_scan(sock)

    prometheus_client.start_http_server(args.port)

    try:
        adv_cache: dict[str, str] = {}

        def handler(mac: str, adv: int, data: bytes, rssi: int) -> None:
            # pylint: disable=unused-argument
            data_str = raw_packet_to_str(data)
            measurement = decode_data_atc1441(adv_cache, mac, data_str)
            if not measurement:
                return

            name = sensors[mac]['name']
            BATTERY.labels(name).set(measurement.battery)
            HUMIDITY.labels(name).set(measurement.humidity)
            TEMPERATURE.labels(name).set(measurement.temperature)
            VOLTAGE.labels(name).set(measurement.voltage)

        parse_le_advertising_events(
            sock,
            handler,
            filter_mac_addrs=tuple(sensors.keys()),
            filter_packet_length=32,
        )
    except KeyboardInterrupt:
        pass
    finally:
        disable_le_scan(sock)


if __name__ == '__main__':
    main()
