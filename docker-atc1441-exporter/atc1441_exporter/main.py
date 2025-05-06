#!/usr/bin/env python3
import argparse
import configparser
import dataclasses
import logging
import signal
from typing import Any
from typing import Optional

import bluetooth._bluetooth as bluez
import prometheus_client
from bluetooth_utils import disable_le_scan
from bluetooth_utils import enable_le_scan
from bluetooth_utils import parse_le_advertising_events
from bluetooth_utils import raw_packet_to_str
from bluetooth_utils import toggle_device


logger = logging.getLogger('app.main')


BATTERY = prometheus_client.Gauge('atc_battery', 'Battery', ['name'])
HUMIDITY = prometheus_client.Gauge('atc_humidity', 'Humidity', ['name'])
TEMPERATURE = prometheus_client.Gauge('atc_temperature', 'Temp.', ['name'])
VOLTAGE = prometheus_client.Gauge('atc_voltage', 'Voltage', ['name'])


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
        return None

    offset = data_idx + len(preamble)
    stripped_data_str = data_str[offset:]
    if len(stripped_data_str) != 26:
        # magic number for length of ATC1441 data
        # TODO: move to parse_le_advertising_events
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
    logging.basicConfig()
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
    enable_le_scan(sock, filter_duplicates=False)

    prometheus_client.start_http_server(args.port)

    try:
        adv_cache: dict[str, str] = {}

        def handler(mac: str, _adv_type: Any, data: Any, _rssi: Any) -> None:
            data_str = raw_packet_to_str(data)
            measurement = decode_data_atc1441(adv_cache, mac, data_str)
            if not measurement:
                return

            name = sensors[mac]['name']
            BATTERY.labels(name).set(measurement.battery)
            HUMIDITY.labels(name).set(measurement.humidity)
            TEMPERATURE.labels(name).set(measurement.temperature)
            VOLTAGE.labels(name).set(measurement.voltage)

        # blocking call (the given handler will be called each time a new LE
        # advertisement packet is detected)
        parse_le_advertising_events(
            sock,
            mac_addr=tuple(sensors.keys()),
            handler=handler,
            debug=False,
        )
    except KeyboardInterrupt:
        pass
    finally:
        disable_le_scan(sock)


if __name__ == '__main__':
    main()
