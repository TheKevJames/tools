Renovate Configurations
=======================

This folder includes all of my shared `Renovate`_ configurations. To make use
of them, you can include the following in your config file (generally
``.github/renovate.json5``):

.. code-block:: json

    {
        "extends": ["github>thekevjames/tools//renovate/presetname.json5"],
    }

For convenience and backwards compatibility, there are a couple pathless
configs stored in the top level of the repo. Those can be used as follows:

.. code-block:: json

    {
        "extends": ["github>thekevjames/tools:presetname"],
    }

You can also use the default config in the root of the repo to get what I think
is a reasonable set of my specific configs, without including anything specific
to my own repos/custom workflows:

.. code-block:: json

    {
        "extends": ["github>thekevjames/tools"],
    }

The full list of available configs is as follows:

* ``//renovate/groups.json5``: group together various items which aren't
  handled by Renovate's builtin ``group:monorepos`` or ``group:recommended``.
  Generally includes: packages with multiple names depending on datasource (eg.
  ``elasticsearch`` and ``org.elasticsearch.client`` for repos with Java and
  Python both), monorepos (eg. ``com.google.auto.value.*``), and packages with
  tight interdependencies (eg. ``fsspec`` and ``gcsfs``, which have exact
  version pins on each other ~90% of the time).
* ``//renovate/versioning.json5``: fix some version persing for various
  dependencies, for example items which don't quite use proper semantic
  versioning or do so with some unusual formatting that Renovate can't properly
  detect. In some cases, this will add support for blocks which could
  previously not been managed: for example, the ``pre-commit`` file's
  ``default_language_version`` block, when set to a ``python`` version, will
  now be managed in the same way as any other use of ``python`` as a
  dependency.
* ``//renovate/custom.json5``: add support for some custom references, eg. to
  allow for managing chunks of configs which need to be manually identified as
  version pins. See comments in the file for usage instructions.
* ``/renovate/semantic-commits.json5``: make renovate use semantic-style
  commits and usage patterns, eg. including not making multiple unrelated
  changes in a single commit.
* ``//renovate/version-as-app.json5``: version the repo as an application, ie.
  with most dependencies being pinned to specific versions rather than
  supporting ranges, to ensure that every installation of the app uses
  explicitly tested applications. You should generally use this for cases where
  your code will not be used as a dependency of any other system but rather
  will be running as a standalaone/isolated application.
* ``/renovate/version-as-lib.json5``: version the repo as an application, ie.
  with most dependencies being set up as supported version ranges and updates
  being set to widen, with the exception of testing/dev dependencies, which
  should always be pinned to ensure all developers can reproduce each other's
  environments.

  * Note that, while I don't recommend it, sometimes a repo may contain
    multiple projects: some which are apps, and some are libs. I would
    recommend splitting things apart, since Renovate doesn't work very well
    with repos that include versioned interdependencies to other local packages
    and can't be coerced to running a subset of it's processing in the required
    DAG. If you want to support this anyway, you can use
    ``//renovate/version-as-app.json5`` as a baseline, then apply a file-based
    override with
    ``//renovate/version-file-as-lib.json5(path-to-library/pyproject.toml)``.

* ``//renovate/automerge.json5``: my prefered automerge rules, eg. for packages
  which I trust to have non-breaking changes. Roughly maps to automerging
  ``minor`` and ``patch`` versions, with the following exceptions:

  * treat ``0.x`` minor updates as potentially breaking
  * denylist some packages which are not well-behaved (eg. maintainers who
    frequently pushing breaking changes as minors or patches)
  * denylist packages which use calver instead of semver
  * allowlist major updates which aren't really major updates (eg. the
    ``gcloud`` cli, which uses the major bump to mean "updated any
    sub-dependency")

* ``//renovate/deprecated.json5``: various deprecated rules which used to be
  members of another preset but are, for whatever reason, being deprecated. See
  the inline comments in this file for migration instructions. If you include
  this file in your config, you should probably also subscribe to notifications
  of any changes to the file.
* ``:personal`` or ``//renovate/personal.json5``: my personal set of configs.
  You probably don't want this.

The following should be considered deprecated and should be updated
accordingly:

* ``:personal``: please update to ``//renovate/personal.json5``
* ``:trustedpackages``: please update to ``//renovate/automerge.json5``

.. _Renovate: https://renovatebot.com/
