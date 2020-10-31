MacPorts Repo
=============

This is a repo of various Portfiles which I use but are not upstream. In the
near future, I'll send 'em to the `right place`_.

The relevant ones are:

* `skhd`_
* `yabai`_
* `youtube-viewer`_

For now, you can install these ports by checking out the repo and running::

    cd ./ports
    echo "file://$(pwd)" | sudo tee -a ${$(which port)%/bin/port}/etc/macports/sources.conf
    portindex

    sudo port install skhd yabai p5-www-youtubeviewer

.. _right place: https://github.com/macports/macports-ports
.. _skhd: https://github.com/koekeishiya/skhd
.. _yabai: https://github.com/koekeishiya/yabai
.. _youtube-viewer: https://github.com/trizen/youtube-viewer
