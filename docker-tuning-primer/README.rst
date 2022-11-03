Docker-Tuning-Primer
====================

|dockerpulls|

Description
-----------

Provides a docker container for the Tuning-Primer script. The container is
based on Alpine Linux, so it should be obnoxiously small.

Note that I am not the maintainer of ``tuning-primer`` itself; please report
any issues with the tool `upstream`_.

You can find the source code in `this Github repo`_.

Usage
-----

Treat this image as if it were the tuning-primer binary. So

.. code-block:: console

    $ docker run --rm -it --link my-mysql-container:mysql thekevjames/tuning-primer all

For full usage information, see the `Tuning-Primer Homepage`_.

.. _Tuning-Primer Homepage: https://launchpad.net/mysql-tuning-primer
.. _this Github repo: https://github.com/TheKevJames/tools/tree/master/docker-tuning-primer
.. _upstream: https://launchpad.net/mysql-tuning-primer

.. |dockerpulls| image:: https://img.shields.io/docker/pulls/thekevjames/tuning-primer.svg?style=flat-square
    :alt: Docker Pulls
    :target: https://hub.docker.com/r/thekevjames/tuning-primer/
