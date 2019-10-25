Docker-Minify
=============

|dockerpulls|

Description
-----------

Provides an (unofficial) docker container for the `minify`_ tool. The container
is based on Alpine Linux, so it should be obnoxiously small.

Usage
-----

This image is meant to be used as a development environment or in CI systems.
For example, if you use CircleCI, you might have:

.. code-block:: yaml

    minify:
        docker:
          - image: thekevjames/minify:v2.5.2
        steps:
          - checkout
          - run: minify --recursive --output build/ src/
          # do something with ./build/

To use this locally, you could do:

.. code-block:: console

    docker run --rm -it \
        -v $(pwd):/app \
        thekevjames/minify:v2.5.2 \
        minify --recursive --output /app/build/ /app/src/

For full usage information, see the `minify`_ documentation.

.. _minify: https://github.com/tdewolff/minify

.. |dockerpulls| image:: https://img.shields.io/docker/pulls/thekevjames/minify.svg?style=flat-square
    :alt: Docker Pulls
    :target: https://hub.docker.com/r/thekevjames/minify/
