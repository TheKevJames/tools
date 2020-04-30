cctui
=====

CCTUI is a CCTray implementation for your terminal -- a live-updating dashboard
of any of your repos.

.. image:: sample.jpg
   :alt: CCTUI sample
   :align: center

Is It Really?
-------------

Well, no. CircleCI's workflows/pipelines feature doesn't work nicely with the
cctray standard and returns the build status of *whichever job happened to run
last* instead of the entire workflow. This project stemmed out of wishing
CCMenu had a terminal UI and worked with CircleCI's workflows... I'll probably
get around to implementing actual cctray support at some point.

You Named It What?
------------------

Yeah, I know. Naming things is hard! I'd be happy to accept ideas :)

Anything Else?
--------------

Well, I have also been itching for a better solution for managing my Github
notifications. Adding a notification dashboard here may or may not end up being
a future feature... I don't like tool bloat, so it may just as well be a
separate project. ¯\\_(ツ)_/¯

Usage
-----

.. code-block:: console

    $ cargo run --release

Use ``j``/``k`` to scroll, ``g``/``G`` for navigating to the top/bottom,
``<enter>`` to open your browser to the selected repo, and ``q`` to quit. You
can force a refresh of all repos with ``r``.

Configuration
-------------

This tool doesn't really make any sense with a default configuration, so you'll
need to edit ``~/.config/cctui/config.yml``:

.. code-block:: yaml

    repos:
    - name: TheKevJames/tools
      circleci:
        branch: cctui-dev
        token: qwer1234asdf5678zxcv
        workflow: run-jobs
    - name: TheKevJames/gnome-shell-extension-transmission-daemon
      circleci:
        token: 1234qwer5678asdf9101
        workflow: integration-tests
      refresh: 120

Basically, ``repos`` accepts a list of items with the following schema:

+-----------------------+--------------------------------------+------------+
| field                 | decription                           | default?   |
+=======================+======================================+============+
| ``name``              | ``<username>/<repo>`` (Github only)  |            |
+-----------------------+--------------------------------------+------------+
| ``circleci.branch``   | name of branch to be tracked         | ``master`` |
+-----------------------+--------------------------------------+------------+
| ``circleci.token``    | personal access token                |            |
+-----------------------+--------------------------------------+------------+
| ``circleci.workflow`` | name of CircleCI workflow to monitor |            |
+-----------------------+--------------------------------------+------------+
| ``refresh``           | refresh interval between updates     | ``30``     |
+-----------------------+--------------------------------------+------------+
