ddtui
=====

DDTUI is a Datadog SLO viewer for your terminal -- a live-updating feed of all
SLOs defined in your application.

You're Awful At Naming Things
-----------------------------

Having done this `twice <../cctui/README.rst>`_ now, I gotta say this terrible
naming scheme is growing on me. Better ideas still gratefully accepted, though!

Usage
-----

.. code-block:: console

    $ poetry install
    $ poetry run ddtui

The keybindings and state is described in the statusbar:

* ``n`` to sort by name
* ``v`` to sort by value (for multi-SLOs, grabs the minimal value)
* ``r`` to reverse the sort order
* ``q`` to quit

Configuration
-------------

You'll need some API keys set in your environment:

.. code-block:: console

    # https://app.datadoghq.com/account/settings#api
    $ export DD_API_KEY=foofoofoofoofoofoofoofoofoofoofo
    # https://app.datadoghq.com/access/application-keys
    $ export DD_APP_KEY=foofoofoofoofoofoofoofoofoofoofoofoofoof
