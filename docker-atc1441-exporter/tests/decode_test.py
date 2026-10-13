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
TRACKED_MAC = bytes.fromhex('a4c138d8f89d')


def ad_structure(ad_type: int, value: bytes) -> bytes:
    return bytes([len(value) + 1, ad_type]) + value


def atc1441_service_data(payload: bytes) -> bytes:
    # UUID 0x181A, little-endian on the wire
    return ad_structure(0x16, bytes.fromhex('1a18') + payload)


def le_advertising_report(
    mac: bytes, ad_structures: Sequence[bytes], rssi: int
) -> bytes:
    ad_data = b''.join(ad_structures)
    params = (
        bytes([0x02, 0x01, 0x00, 0x00])  # subevent, reports, ev, addr
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


def tracked_advert(*ad_structures: bytes) -> bytes:
    return le_advertising_report(TRACKED_MAC, ad_structures, -60)


def nothing_exported(registry: prometheus_client.CollectorRegistry) -> bool:
    return not any(metric.samples for metric in registry.collect())


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


@pytest.mark.parametrize(
    ('payload', 'expected'),
    [
        (
            ATC_PAYLOAD,
            main.Measurement(
                battery=85, humidity=48, temperature=23.4, voltage=2.95
            ),
        ),
        (
            bytes.fromhex('a4c138d8f89dff9c1a640bb801'),
            main.Measurement(
                battery=100, humidity=26, temperature=-10.0, voltage=3.0
            ),
        ),
    ],
)
def test_decode_data_atc1441(
    payload: bytes, expected: main.Measurement
) -> None:
    assert main.decode_data_atc1441({}, 'a4:c1:38:d8:f8:9d', payload) == (
        expected
    )


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
    'data',
    [
        pytest.param(b'', id='empty'),
        pytest.param(b'\x02' + ATC_EVENT[1:], id='not-an-hci-event'),
        pytest.param(ATC_EVENT[:13], id='undecodable'),
        pytest.param(
            le_advertising_report(
                bytes.fromhex('a4c138000000'),
                [atc1441_service_data(ATC_PAYLOAD)],
                -60,
            ),
            id='untracked-device',
        ),
        pytest.param(tracked_advert(FLAGS_AD), id='no-service-data'),
        pytest.param(
            tracked_advert(
                ad_structure(0x16, bytes.fromhex('1b18') + ATC_PAYLOAD)
            ),
            id='other-service-uuid',
        ),
        pytest.param(
            tracked_advert(atc1441_service_data(ATC_PAYLOAD[:-1])),
            id='short-payload',
        ),
        pytest.param(
            tracked_advert(atc1441_service_data(ATC_PAYLOAD + b'\x00')),
            id='long-payload',
        ),
    ],
)
def test_processor_ignores_unusable_events(data: bytes) -> None:
    registry, process = processor_for('a4:c1:38:d8:f8:9d')

    process(data)

    assert nothing_exported(registry)


@hypothesis.strategies.composite
def hci_packets(draw: hypothesis.strategies.DrawFn) -> bytes:
    prefix = draw(
        hypothesis.strategies.sampled_from(
            [
                b'',
                bytes.fromhex('043e'),
                bytes.fromhex('040e'),
                bytes.fromhex('043eff0201') + bytes(2) + TRACKED_MAC[::-1],
                bytes.fromhex('043eff0d01'),
            ]
        )
    )
    ads = draw(
        hypothesis.strategies.lists(
            hypothesis.strategies.builds(
                ad_structure,
                hypothesis.strategies.sampled_from([0x01, 0x09, 0x16, 0x20])
                | hypothesis.strategies.integers(0, 255),
                hypothesis.strategies.binary(max_size=31),
            ),
            max_size=4,
        )
    )
    packet = prefix + b''.join(ads)
    cut = draw(hypothesis.strategies.integers(0, len(packet)))
    return packet[:cut] + draw(hypothesis.strategies.binary(max_size=64))


@hypothesis.given(data=hci_packets())
def test_processor_survives_arbitrary_packets(data: bytes) -> None:
    _, process = processor_for('a4:c1:38:d8:f8:9d')

    process(data)


# Captured from sensor ATC_D8F89D via CoreBluetooth, which exposes only the
# 0x181A service-data payload (and RSSI); the HCI framing around it is
# hand-built. All report 25.7C, 53%RH, 34% battery, 2475mV.
CAPTURED = [
    (bytes.fromhex('a4c138d8f89d0101352209ab54'), -65),
    (bytes.fromhex('a4c138d8f89d0101352209ab57'), -66),
    (bytes.fromhex('a4c138d8f89d0101352209ab59'), -68),
    (bytes.fromhex('a4c138d8f89d0101352209ab5a'), -67),
    (bytes.fromhex('a4c138d8f89d0101352209ab5c'), -65),
]
CAPTURED_EXPORT = {
    'battery': 34,
    'humidity': 53,
    'temperature': 25.7,
    'voltage': 2.475,
}


def captured_event(payload: bytes, rssi: int) -> bytes:
    return le_advertising_report(
        payload[:6], [FLAGS_AD, atc1441_service_data(payload)], rssi
    )


@pytest.mark.parametrize(('payload', 'rssi'), CAPTURED)
def test_processor_exports_captured_advert(payload: bytes, rssi: int) -> None:
    registry, process = processor_for('a4:c1:38:d8:f8:9d')

    process(captured_event(payload, rssi))

    assert exported(registry, 'sensor') == CAPTURED_EXPORT


def test_processor_dedupes_captured_adverts_by_counter() -> None:
    registry, process = processor_for('a4:c1:38:d8:f8:9d')

    def chilled(payload: bytes) -> bytes:
        return payload[:6] + struct.pack('>h', -50) + payload[8:]

    for payload, rssi in CAPTURED:
        process(captured_event(payload, rssi))
        assert exported(registry, 'sensor') == CAPTURED_EXPORT

        process(captured_event(chilled(payload), rssi))
        assert exported(registry, 'sensor') == CAPTURED_EXPORT

    last_payload, last_rssi = CAPTURED[-1]
    fresh = chilled(last_payload)[:-1] + b'\x5d'
    process(captured_event(fresh, last_rssi))
    assert exported(registry, 'sensor')['temperature'] == -5.0
