import configparser
import struct
from collections.abc import Callable
from collections.abc import Sequence

import hypothesis
import hypothesis.strategies
import prometheus_client
import pytest

from atc1441_exporter import main
from atc1441_exporter._aioblescan import events

# A real-shape ATC1441 LE advertising-report HCI event: sensor
# A4:C1:38:D8:F8:9D reporting 23.4 C, 48 %RH, 85 % battery, 2.950 V,
# advertising counter 0x0a, at RSSI -59. The 0x181A service-data payload is the
# 13 bytes after '161a18': mac(6) temp(2) hum(1) bat(1) mVolt(2) counter(1) =
#   a4c138d8f89d 00ea 30 55 0b86 0a
ATC_EVENT = bytes.fromhex(
    '043e1d020103009df8d838c1a41110161a18a4c138d8f89d00ea30550b860ac5'
)
ATC_PAYLOAD = bytes.fromhex('a4c138d8f89d00ea30550b860a')

FLAGS_AD = bytes.fromhex('020106')


def ad_structure(ad_type: int, value: bytes) -> bytes:
    return bytes([len(value) + 1, ad_type]) + value


def atc1441_service_data(payload: bytes) -> bytes:
    # UUID 0x181A, little-endian on the wire
    return ad_structure(0x16, bytes.fromhex('1a18') + payload)


def le_advertising_report(
    mac: bytes, ad_structures: Sequence[bytes], rssi: int, event_type: int = 0
) -> bytes:
    ad_data = b''.join(ad_structures)
    params = (
        bytes([0x02, 0x01, event_type, 0x00])  # subevent, reports, ev, addr
        + mac[::-1]
        + bytes([len(ad_data)])
        + ad_data
        + struct.pack('>b', rssi)
    )
    return bytes([0x04, 0x3E, len(params)]) + params


def exported(
    registry: prometheus_client.CollectorRegistry, name: str
) -> dict[str, float | None]:
    return {
        metric: registry.get_sample_value(f'atc_{metric}', {'name': name})
        for metric in ('battery', 'humidity', 'temperature', 'voltage')
    }


def processor_for(
    mac: str,
) -> tuple[prometheus_client.CollectorRegistry, Callable[[bytes], None]]:
    sensors = configparser.ConfigParser()
    sensors[mac] = {'name': 'sensor'}
    registry = prometheus_client.CollectorRegistry()
    return registry, main.build_processor(sensors, registry)


@hypothesis.strategies.composite
def macs(draw: hypothesis.strategies.DrawFn) -> bytes:
    # Plant the service data header (16 1a 18) in some addresses, both byte-
    # and nibble-aligned on the wire (where the address is byte-reversed):
    # random bytes would almost never produce it.
    needle = draw(
        hypothesis.strategies.sampled_from(
            [b'', bytes.fromhex('181a16'), bytes.fromhex('8fa161f1')]
        )
    )
    filler = draw(
        hypothesis.strategies.binary(
            min_size=6 - len(needle), max_size=6 - len(needle)
        )
    )
    split = draw(hypothesis.strategies.integers(0, len(filler)))
    return filler[:split] + needle + filler[split:]


@hypothesis.given(
    mac=macs(),
    temperature=hypothesis.strategies.integers(-(2**15), 2**15 - 1),
    humidity=hypothesis.strategies.integers(0, 255),
    battery=hypothesis.strategies.integers(0, 255),
    millivolts=hypothesis.strategies.integers(0, 2**16 - 1),
    counter=hypothesis.strategies.integers(0, 255),
    rssi=hypothesis.strategies.integers(-128, 127),
    with_flags=hypothesis.strategies.booleans(),
    name_position=hypothesis.strategies.sampled_from([None, 0, 1]),
)
@hypothesis.example(
    mac=bytes.fromhex('a4c18fa161f1'),
    temperature=257,
    humidity=53,
    battery=34,
    millivolts=2475,
    counter=0x54,
    rssi=-65,
    with_flags=True,
    name_position=None,
)
def test_processor_exports_advertised_values(
    mac: bytes,
    temperature: int,
    humidity: int,
    battery: int,
    millivolts: int,
    counter: int,
    rssi: int,
    with_flags: bool,
    name_position: int | None,
) -> None:
    payload = mac + struct.pack(
        '>hBBHB', temperature, humidity, battery, millivolts, counter
    )
    ads = [atc1441_service_data(payload)]
    if name_position is not None:
        name = f'ATC_{mac[3:].hex().upper()}'.encode()
        ads.insert(name_position, ad_structure(0x09, name))
    if with_flags:
        ads.insert(0, FLAGS_AD)
    registry, process = processor_for(':'.join(f'{b:02x}' for b in mac))

    process(le_advertising_report(mac, ads, rssi))

    assert exported(registry, 'sensor') == {
        'battery': battery,
        'humidity': humidity,
        'temperature': temperature / 10,
        'voltage': millivolts / 1000,
    }


def test_vendored_parser_extracts_advert_fields() -> None:
    event = events.HCI_Event()
    event.decode(ATC_EVENT)

    assert event.retrieve('peer')[0].val == 'a4:c1:38:d8:f8:9d'
    assert event.retrieve('rssi')[0].val == -59
    assert main.atc1441_service_data(event) == ATC_PAYLOAD


def test_decode_data_atc1441_end_to_end() -> None:
    measurement = main.decode_data_atc1441(
        {}, 'a4:c1:38:d8:f8:9d', ATC_PAYLOAD
    )

    assert measurement == main.Measurement(
        battery=85, humidity=48, temperature=23.4, voltage=2.95
    )


def test_decode_data_atc1441_dedupes_by_advertising_counter() -> None:
    mac = 'a4:c1:38:d8:f8:9d'
    cache: dict[str, int] = {}
    assert main.decode_data_atc1441(cache, mac, ATC_PAYLOAD) is not None
    # same advertising counter -> deduplicated
    assert main.decode_data_atc1441(cache, mac, ATC_PAYLOAD) is None


def test_processor_matches_uppercase_config_sections() -> None:
    # The vendored parser emits lowercase MACs; users write uppercase section
    # headers per the README, so the processor must match case-insensitively.
    sensors = configparser.ConfigParser()
    sensors['A4:C1:38:D8:F8:9D'] = {'name': 'Living Room'}
    registry = prometheus_client.CollectorRegistry()

    process = main.build_processor(sensors, registry)
    process(ATC_EVENT)

    assert (
        registry.get_sample_value('atc_temperature', {'name': 'Living Room'})
        == 23.4
    )


@pytest.mark.parametrize(
    'payload', [b'', ATC_PAYLOAD[:-1], ATC_PAYLOAD + b'\x00']
)
def test_decode_data_atc1441_rejects_invalid_length(payload: bytes) -> None:
    assert main.decode_data_atc1441({}, 'a4:c1:38:d8:f8:9d', payload) is None
