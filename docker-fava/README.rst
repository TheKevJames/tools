fava
====

|dockerpulls|

Description
-----------

Provides a docker container for the Fava project. The container is based on
Alpine Linux, so it should be obnoxiously small.

Note that I am not the maintainer of ``fava`` itself, please report any issues
with the tool `upstream`_.

You can find the source code in `this Github repo`_.

Tag description:

* ``latest``: whatever is the most recent build on master
* ``\d+.\d+.\d+``: the latest build for a given fava version
* in addition, each commit has its commit hash user as a docker tag

Usage
-----

You can run this image via:

.. code-block:: console

    $ docker run --rm -it -p 5000:5000 -v/my/beancount:/data thekevjames/fava:latest /data/index.beancount

or via `quay.io`_:

.. code-block:: console

    $ docker run --rm -it -p 5000:5000 -v/my/beancount:/data quay.io/thekevjames/fava:latest /data/index.beancount

For full usage information, see the `Getting Started Guide`_.

Releasing
---------

Whenever a new release of MySQLTuner is pushed, this library is updated
accordingly (edit ``FAVA_VERSION``).

.. _Getting Started Guide: https://beancount.github.io/fava/usage.html
.. _quay.io: https://quay.io/repository/thekevjames/fava
.. _this Github repo: https://github.com/TheKevJames/tools/tree/master/docker-fava
.. _upstream: https://github.com/beancount/fava/

.. |dockerpulls| image:: https://img.shields.io/docker/pulls/thekevjames/fava.svg?style=flat-square
    :alt: Docker Pulls
    :target: https://hub.docker.com/r/thekevjames/fava/
