gcloud-pubsub-emulator
======================

|dockerpulls|

Description
-----------

This image was based on `marcelcorso/gcloud-pubsub-emulator`_, updated to
auto-build off of every new ``gcloud`` release. We also include an updated
version of the `pubsubc`_ tool, which supports a wider range of usecases around
initializing various topics/subscriptions on startup.

You can find the source code in `this Github repo`_.

Tag description:

* ``latest``: whatever is the most recent build on master
* ``\d+.\d+.\d+``: the latest build for a given gcloud version
* in addition, each commit has its commit hash user as a docker tag

Usage
-----

You can run this image via:

.. code-block:: console

    $ docker run --rm -it -p 8681:8681 thekevjames/gcloud-pubsub-emulator:latest

or via `quay.io`_:

.. code-block:: console

    $ docker run --rm -it -p 8681:8681 quay.io/thekevjames/gcloud-pubsub-emulator:latest

If you plan to create topics/subscriptions automatically on startup (see
`Automatic Topic and Subscription Creation`_ below), you may also want to
expose port 8682 for liveness probes. See the section on `Liveness Probes`_ for
more info.

Once the image is running, you can point your application code to the emulator
via:

.. code-block:: console

    $ export PUBSUB_EMULATOR_HOST=localhost:8681
    $ ./my_app

Automatic Topic and Subscription Creation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This image also provides the ability to create topics and subscriptions in
projects on startup. The preferred method of doing so is by creating a
configuration json file, the location of which defaults to
``/etc/pubsubc/config.json``. The location of this file can be overwritten by
setting the ``$PUBSUBC_CONFIG`` environment variable::

    docker run \
        -ePUBSUBC_CONFIG=/foo/bar.json -v./my-config.json:/foo/bar.json \
        quay.io/thekevjames/gcloud-pubsub-emulator:latest

The config file should be a list of objects containing topic configurations::

    [
      {
        "topic": "topic1",
        "project": "project1"
      },
      {
        "topic": "topic2",
        "project": "project1",
        "subscriptions": [
          {
            "name": "subscription1",
            "push_endpoint": "http://localhost:3001/messages"
          },
          {
            "name": "subscription2"
          }
        ]
      }
    ]

You must specify at least one ``topic``. A ``topic`` must include a ``project``
key, and may optionally include a list of ``subscription`` details which will
be attached to that topic. A subscription will be created in push mode if a
``push_endpoint`` is provided, otherwise it will be a pull subscription.

See `config.json`_ for a sample configuration file.

Environment Variables
^^^^^^^^^^^^^^^^^^^^^

You may also use environment variables to specify the above configuration. Note
that environment variables are only checked if no configuration file is
provided: if you specify a configuration file, you must use it for all of your
configurations.

Note that environment variables do not support configuring push subscriptions.

To use environment variables, specify ``$PUBSUB_PROJECT`` with a sequential
number appended to it, *starting with 1* (for example: your first project
configuration should be ``$PUBSUB_PROJECT1``). The format of the environment
variable is as follows::

   PROJECTID,TOPIC1,TOPIC2:SUBSCRIPTION1:SUBSCRIPTION2,TOPIC3:SUBSCRIPTION3

A comma-separated list where the first item is the *project ID* and the rest
are topics. The topics themselves are colon-separated where the first item is
the *topic ID* and the rest are *subscription IDs*. A topic doesn't necessarily
need to specify any subscriptions.

For example, if you have *project ID* ``company-dev``, with topic ``invoices``
that has a subscription ``invoice-calculator``, another topic ``chats`` with
subscriptions ``slack-out`` and ``irc-out`` and a third topic ``notifications``
without any subscriptions, you could define it this way:

.. code-block:: console

   $ PUBSUB_PROJECT1=company-dev,invoices:invoice-calculator,chats:slack-out:irc-out,notifications

So the full command would look like:

.. code-block:: console

   $ docker run --rm -it \
         -p 8681:8681 \
         -e PUBSUB_PROJECT1=company-dev,invoices:invoice-calculator,chats:slack-out:irc-out,notifications \
         thekevjames/gcloud-pubsub-emulator:latest

If you want to define more projects, you'd simply add a ``PUBSUB_PROJECT2``,
``PUBSUB_PROJECT3``, etc.

As with configuring this script via config file, you must have at least one
configured ``topic``.

Liveness Probes
~~~~~~~~~~~~~~~

When this image starts up it will first make the emulator available on port
8681, then will (optionally) create any specified topics/subscriptions and
begin to respond on port 8682. As such, you can implement a liveness probe by
checking is the relevant port is available: 8681 for a standard configuration
or 8682 for any time you've set a ``PUBSUB_PROJECT*`` variable or provided a
configuration json.

You may find `wait-for`_ or `wait-for-it`_ useful for this purpose. If you use
some other tool for readiness probes, any check for whether the port is bound
will work. Some examples include:

* ``nc -z 127.0.0.1 8681``
* ``true &>/dev/null </dev/tcp/127.0.0.1/8681`` (requires ``bash``)
* ``lsof -i :8681``
* ``netstat -an | grep LISTEN | grep :8681``
* ``wget 127.0.0.1:8681``
* ``ss | grep LISTEN | grep :8681``
* ``nmap -sS -O -p8681 127.0.0.1``
* ``exec 6<>/dev/tcp/127.0.0.1/8681`` (requires ``bash``)

.. _marcelcorso/gcloud-pubsub-emulator: https://github.com/marcelcorso/gcloud-pubsub-emulator
.. _pubsubc: https://github.com/prep/pubsubc
.. _this Github repo: https://github.com/TheKevJames/tools/tree/master/docker-gcloud-pubsub-emulator
.. _config.json: https://github.com/TheKevJames/tools/tree/master/docker-gcloud-pubsub-emulator/config.json
.. _quay.io: https://quay.io/repository/thekevjames/tuning-primer
.. _wait-for-it: https://github.com/vishnubob/wait-for-it
.. _wait-for: https://github.com/eficode/wait-for

.. |dockerpulls| image:: https://img.shields.io/docker/pulls/thekevjames/gcloud-pubsub-emulator.svg?style=flat-square
    :alt: Docker Pulls
    :target: https://hub.docker.com/r/thekevjames/gcloud-pubsub-emulator/
