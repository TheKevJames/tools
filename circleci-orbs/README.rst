CircleCI Orbs
=============

A bunch of `CircleCI orbs`_ for various occasions. Production-ready.

All of these orbs are available in the `Orb Registry`_ along with documentation
and usage. More specifically, you can find:

* `thekevjames/linter`_, including support for `pre-commit`_.
* `thekevjames/pytest`_, including support for PyTest.
* `thekevjames/deployment-notifier`_, including support for Slack and Sentry.

Usage
-----

Simply include the ``orb`` or ``orbs`` you're interested in within your
``.circleci/config.yml`` file:

.. code-block:: yaml

    version: 2.1
    orbs:
      linter: thekevjames/linter@0
      pytest: thekevjames/pytest@0
      notifier: thekevjames/deployment-notifier@0

    # ... the rest of your config

.. _CircleCI Orbs: https://circleci.com/orbs/
.. _Org Registry: https://circleci.com/orbs/registry/?query=thekevjames&filterBy=all
.. _pre-commit: https://pre-commit.com/
.. _thekevjames/linter: https://circleci.com/orbs/registry/orb/thekevjames/linter
.. _thekevjames/pytest: https://circleci.com/orbs/registry/orb/thekevjames/pytest
