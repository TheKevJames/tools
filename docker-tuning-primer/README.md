# Docker-Tuning-Primer

[![ImageLayers Size](https://img.shields.io/imagelayers/image-size/thekevjames/tuning-primer/latest.svg)](https://hub.docker.com/r/thekevjames/tuning-primer/)
[![Docker Pulls](https://img.shields.io/docker/pulls/thekevjames/tuning-primer.svg)](https://hub.docker.com/r/thekevjames/tuning-primer/)

## Description

Provides a docker container for the Tuning-Primer script. The container is based on alpine, so it should be obnoxiously small.

## Usage

Treat this image as if it were the tuning-primer binary. So

    export MY_MYSQL_CONTAINER=mysql-container
    docker pull thekevjames/tuning-primer
    docker run --rm --link $MY_MYSQL_CONTAINER:mysql thekevjames/tuning-primer all

For full usage information, see the [Tuning-Primer Homepage](https://launchpad.net/mysql-tuning-primer).
