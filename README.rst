Various Tools
=============

This repository is a collection of tools too small to be worth managing as
their own repo. Many of these originally started as an `experiment`_ or, before
I started trying to organize my GitHub presence, as a couple-line repo I'd
completely forgotten about.

- `32-bit Ubuntu Docker Images`_
- `ATC1441 OpenMetrics Exporter`_
- `CCTUI`_
- `CSS UserStyles`_
- `DDTUI`_
- `Dockerized caddy + caddy-security`_
- `Dockerized Fava`_
- `Dockerized gcloud Pubsub Emulator`_
- `Dockerized MySQLTuner`_
- `Dockerized Nox`_
- `Dockerized Tuning-Primer`_
- `Slack Notifier`_

Renovate
--------

This repository also contains my `Renovate`_ configurations, which are shared
across all my projects. You can grab the common "make it work for anything
Kevin has done anywhere" config with:

.. code-block:: json

    {
        "extends": ["github>thekevjames/tools"]
    }

.. _ATC1441 OpenMetrics Exporter: https://github.com/TheKevJames/tools/tree/master/docker-atc1441-exporter
.. _32-bit Ubuntu Docker Images: https://github.com/TheKevJames/tools/tree/master/docker-ubuntu32
.. _CCTUI: https://github.com/TheKevJames/tools/tree/master/cctui
.. _CSS UserStyles: https://github.com/TheKevJames/tools/tree/master/userstyles
.. _DDTUI: https://github.com/TheKevJames/tools/tree/master/ddtui
.. _Dockerized MySQLTuner: https://github.com/TheKevJames/tools/tree/master/docker-mysqltuner
.. _Dockerized Fava: https://github.com/TheKevJames/tools/tree/master/docker-fava
.. _Dockerized Nox: https://github.com/TheKevJames/tools/tree/master/docker-nox
.. _Dockerized Tuning-Primer: https://github.com/TheKevJames/tools/tree/master/docker-tuning-primer
.. _Dockerized caddy + caddy-security: https://github.com/TheKevJames/tools/tree/master/docker-caddy-security
.. _Dockerized gcloud Pubsub Emulator: https://github.com/TheKevJames/tools/tree/master/docker-gcloud-pubsub-emulator
.. _Renovate: https://renovatebot.com/
.. _Slack Notifier: https://github.com/TheKevJames/tools/tree/master/slack-notifier
.. _experiment: https://github.com/TheKevJames/experiments
