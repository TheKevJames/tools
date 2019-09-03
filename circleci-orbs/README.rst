CircleCI Orbs
=============

A bunch of `CircleCI orbs`_ for various occasions. Production-ready.

All of these orbs are available in the `Orb Registry`_ along with documentation
and usage. More specifically, you can find:

* `thekevjames/linter`_, including support for `pre-commit`_.
* `thekevjames/tester`_, including support for `pytest`_.
* `thekevjames/notifier`_, including support for Datadog, Sentry, and Slack.

It also includes a few deprecated orbs:

* `thekevjames/deployment-notifier`_, subsumed by `thekevjames/notifier`_.
* `thekevjames/pytest`_, subsumed by `thekevjames/tester`_.

Usage
-----

Simply include the ``orb`` or ``orbs`` you're interested in within your
``.circleci/config.yml`` file:

.. code-block:: yaml

    version: 2.1
    orbs:
      linter: thekevjames/linter@1
      tester: thekevjames/tester@1
      notifier: thekevjames/notifier@1

    # ... the rest of your config

.. _CircleCI Orbs: https://circleci.com/orbs/
.. _Orb Registry: https://circleci.com/orbs/registry/?query=thekevjames&filterBy=all
.. _pre-commit: https://pre-commit.com/
.. _pytest: https://docs.pytest.org/en/latest/
.. _thekevjames/deployment-notifier: https://circleci.com/orbs/registry/orb/thekevjames/deployment-notifier
.. _thekevjames/linter: https://circleci.com/orbs/registry/orb/thekevjames/linter
.. _thekevjames/notifier: https://circleci.com/orbs/registry/orb/thekevjames/notifier
.. _thekevjames/pytest: https://circleci.com/orbs/registry/orb/thekevjames/pytest
.. _thekevjames/tester: https://circleci.com/orbs/registry/orb/thekevjames/tester
