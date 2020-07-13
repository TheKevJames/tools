Slack Notifier
==============

This is a simple script for sending deployment notifications from CircleCI to
a Slack instance. Zero-dependencies (besides ``sh``)!

Usage
-----

You must have ``SLACK_DEPLOYBOT_WEBHOOK`` set in your environment settings (or
via the ``-w`` flag).

.. code-block:: yaml

    # ...
    - deploy:
        name: send post-deployment notification
        command: |
          curl https://raw.githubusercontent.com/TheKevJames/tools/master/slack-notifier/send-deploy-notif.sh > send-deploy-notif.sh
          sh send-deploy-notif.sh

The script will attempt to load all values from the environment. You can also
pass the following values explicitly:

.. code-block:: console

    $ sh send-deploy-notif.sh -d "${DIFF_URL}"
    # sh send-deploy-notif.sh -e "${ENVIRONMENT}"
    $ sh send-deploy-notif.sh -n "${PROJECT_NAME}"
    $ sh send-deploy-notif.sh -p "${PREVIOUS_VERSION}"
    $ sh send-deploy-notif.sh -u "${USER}"
    $ sh send-deploy-notif.sh -v "${NEW_VERSION}"

CircleCI
~~~~~~~~

On CircleCI, we pull in the ``$CIRCLE_COMPARE_URL`` variable to generate diff
links (assuming you don't provide that optional manually).

Note that value was removed from v2.1 of the CircleCI spec in favor of
pipeline values; fortunately, you can use the latter to generate the former:

.. code-block:: yaml

    environment:
      CIRCLE_COMPARE_URL: <<pipeline.project.git_url>>/compare/<<pipeline.git.base_revision>>..<<pipeline.git.revision>>
