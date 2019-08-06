Various Tools
=============

This repository is a collection of tools too small to be worth managing as
their own repo. Many of these originally started as an `experiment`_ or, before
I started trying to organize my GitHub presence, as a couple-line repo I'd
completely forgotten about.

- `32-bit Ubuntu Docker Images`_
- `CircleCI Orbs`_
- `Dockerized MySQLTuner`_
- `Dockerized Nox`_
- `Dockerized Tuning-Primer`_
- `Slack Notifier`_

This repository also contains my `Renovate`_ configurations, which are shared
across all my projects. You can get the full configuration (which is a bit
catered to my personal workflow) with:

.. code-block:: json

    {
        "extends": ["github>thekevjames/tools:personal"]
    }

Or use only the common "make it work for anything Kevin has done anywhere"
config with:

.. code-block:: json

    {
        "extends": ["github>thekevjames/tools"]
    }

.. _32-bit Ubuntu Docker Images: https://github.com/TheKevJames/tools/tree/master/docker-ubuntu32
.. _CircleCI Orbs: https://github.com/TheKevJames/tools/tree/master/circleci-orbs
.. _Dockerized MySQLTuner: https://github.com/TheKevJames/tools/tree/master/docker-mysqltuner
.. _Dockerized Nox: https://github.com/TheKevJames/tools/tree/master/docker-nox
.. _Dockerized Tuning-Primer: https://github.com/TheKevJames/tools/tree/master/docker-tuning-primer
.. _experiment: https://github.com/TheKevJames/experiments
.. _Renovate: https://renovatebot.com/
.. _Slack Notifier: https://github.com/TheKevJames/tools/tree/master/slack-notifier
