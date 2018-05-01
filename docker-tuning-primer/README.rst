Docker-MySQLTuner
=================

|imagelayers| |dockerpulls|

Description
-----------

Provides a docker container for the Tuning-Primer script. The container is
based on Alpine Linux, so it should be obnoxiously small.

Usage
-----

Treat this image as if it were the tuning-primer binary. So

.. code-block:: console

    $ docker run --rm -it --link my-mysql-container:mysql thekevjames/tuning-primer all

For full usage information, see the `Tuning-Primer Homepage`_.

.. _Tuning-Primer Homepage: https://launchpad.net/mysql-tuning-primer
.. |dockerpulls| image:: https://img.shields.io/docker/pulls/thekevjames/tuning-primer.svg?style=flat-square
    :alt: Docker Pulls
    :target: https://hub.docker.com/r/thekevjames/tuning-primer/
.. |imagelayers| image:: https://img.shields.io/imagelayers/image-size/thekevjames/tuning-primer/latest.svg?style=flat-square
    :alt: ImageLayers Size
    :target: https://hub.docker.com/r/thekevjames/tuning-primer/
