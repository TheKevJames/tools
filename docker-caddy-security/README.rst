caddy-security
==============

|dockerpulls|

An auto-building and updating build of `caddy`_, with the `caddy-security`_
module built in.

You can find the source code in `this Github repo`_.

Tag description:

* ``latest``: whatever is the most recent build on master
* ``\d+.\d+.\d+-\d+.\d+.\d+``: the latest build for given caddy and
  caddy-security versions
* in addition, each commit has its commit hash user as a docker tag

Usage
-----

Swap it in anywhere you had previously been using
``docker.io/library/caddy:2-alpine``.

.. _caddy-security: https://github.com/greenpau/caddy-security
.. _caddy: https://caddyserver.com/
.. _this Github repo: https://github.com/TheKevJames/tools/tree/master/docker-caddy-security

.. |dockerpulls| image:: https://img.shields.io/docker/pulls/thekevjames/caddy-security.svg?style=flat-square
    :alt: Docker Pulls
    :target: https://hub.docker.com/r/thekevjames/caddy-security/
