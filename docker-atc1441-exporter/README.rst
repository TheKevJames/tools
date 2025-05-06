atc1441-exporter
================

|dockerpulls|

A simple OpenMetrics Exporter responsible for handling ATC1441 sensor data via
BLE advertisements.

Heavily inspired by `MiTemperature2`_, `xiaomi-sensor-exporter`_, and
`atc-prometheus-exporter`_; this script combines the passive/low-power scanning
from former with the OpenMetrics scrapability of the latter two.

Special thank you as well to `py-bluetooth-utils`_, which has been vendored in.

Usage
-----

First off, you'll need to flash your devices with ATC1441-compatible firmware.
The canonical source, in my opinion would be from `pvvx/ATC_MiThermometer`_.
Once you've followed the instructions and flashed your device, swap the
advertising format over to ATC.

Then, create a ``config.ini`` with the sensors you want to scrape. While you're
flashing them, you can grab their MAC addresses from the same page (just remove
the last two bytes and add the relevant colons). Mine looks like:

.. code-block:: ini

    [A4:C1:38:D8:F8:9D]
    name=Living Room

    [A4:C1:38:BF:95:E9]
    name=Studio

Once this file exists, you can run the app. The easiest thing to do is to run
it via docker, but if you want to run it locally, you can check the Dockerfile
for the relevant dependencies.

.. code-block:: console

    docker run --rm -it --net=host --privileged -v/path/to/config.ini:/app/config.ini quay.io/thekevjames/atc1441-exporter:latest /app/config.ini

Or, for example, as a docker compose service:

.. code-block:: yaml

    atc1441-exporter:
        container_name: atc1441-exporter
        image: quay.io/thekevjames/atc1441-exporter:latest
        command: /app/config.ini
        restart: unless-stopped
        network_mode: host
        privileged: true
        volumes:
            - ./atc1441.ini:/app/config.ini:Z

There are a few optional flags you can pass in the command::

    --interface | -i        Hardware interface, eg. hciX [default: 0]
    --port | -p             OpenMetrics listen port [default: 8000]

.. _MiTemperature2: https://github.com/JsBergbau/MiTemperature2
.. _atc-prometheus-exporter: https://github.com/kroemeke/atc-prometheus-exporter
.. _pvvx/ATC_MiThermometer: https://github.com/pvvx/ATC_MiThermometer
.. _py-bluetooth-utils: https://github.com/colin-guyon/py-bluetooth-utils
.. _xiaomi-sensor-exporter: https://github.com/vicziani/xiaomi-sensor-exporter

.. |dockerpulls| image:: https://img.shields.io/docker/pulls/thekevjames/atc1441-exporter.svg?style=flat-square
    :alt: Docker Pulls
    :target: https://hub.docker.com/r/thekevjames/atc1441-exporter/
