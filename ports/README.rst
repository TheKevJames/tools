MacPorts Repo
=============

This is a repo including the various Portfiles I've built for myself. They are
all in review pending inclusion upstream, at which point this folder will be
deleted.

The relevant ones are:

* `skhd`_ (`PR <https://github.com/macports/macports-ports/pull/9005>`__)
* `yabai`_ (`PR <https://github.com/macports/macports-ports/pull/9006>`__)
* `youtube-viewer`_ (`PR <https://github.com/macports/macports-ports/pull/9004>`__)

For now, you can install these ports by checking out the repo and running::

    cd ./ports
    echo "file://$(pwd)" | sudo tee -a ${$(which port)%/bin/port}/etc/macports/sources.conf
    portindex

    sudo port install skhd yabai p5-www-youtubeviewer

.. _right place: https://github.com/macports/macports-ports
.. _skhd: https://github.com/koekeishiya/skhd
.. _yabai: https://github.com/koekeishiya/yabai
.. _youtube-viewer: https://github.com/trizen/youtube-viewer
