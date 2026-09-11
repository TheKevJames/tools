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


def test_vendored_parser_extracts_advert_fields() -> None:
    event = events.HCI_Event()
    event.decode(ATC_EVENT)

    assert event.retrieve('peer')[0].val == 'a4:c1:38:d8:f8:9d'
    assert event.retrieve('rssi')[0].val == -59
    assert event.raw_data is not None
    assert main.ATC_PREAMBLE in event.raw_data.hex()


def test_decode_data_atc1441_end_to_end() -> None:
    event = events.HCI_Event()
    event.decode(ATC_EVENT)
    assert event.raw_data is not None

    measurement = main.decode_data_atc1441(
        {}, event.retrieve('peer')[0].val, event.raw_data.hex()
    )

    assert measurement == main.Measurement(
        battery=85, humidity=48, temperature=23.4, voltage=2.95
    )


def test_decode_data_atc1441_dedupes_by_advertising_counter() -> None:
    event = events.HCI_Event()
    event.decode(ATC_EVENT)
    assert event.raw_data is not None
    mac = event.retrieve('peer')[0].val
    data_str = event.raw_data.hex()

    cache: dict[str, str] = {}
    assert main.decode_data_atc1441(cache, mac, data_str) is not None
    # same advertising counter -> deduplicated
    assert main.decode_data_atc1441(cache, mac, data_str) is None


@pytest.mark.parametrize(
    'data_str',
    [
        '',  # empty
        'deadbeef',  # no preamble
        '161a18a4c138',  # preamble but truncated payload
    ],
)
def test_decode_data_atc1441_rejects_invalid(data_str: str) -> None:
    assert main.decode_data_atc1441({}, 'a4:c1:38:d8:f8:9d', data_str) is None
