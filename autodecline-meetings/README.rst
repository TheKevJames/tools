Autodecline Meetings for Google Calendar
========================================

``lib/`` defines a Google App Script library which can be used to automatically
decline meetings to your Google Calendar.

To use the library, I need to share it with you (or, alternatively, you can
create your own copy with the given sources). Then, you'll need to
`create a new App Script <https://script.google.com/home>`_ .

In that script, you can import my library by pasting the following script ID:
``1p1vR9nPlG6TZ9gp4F97p7Q9Yq9lxos6NLvQbQC1qRKoHtcriSiaY0Sf9`` after pressing
the ``+`` next to ``Libraries``. You'll also need to hit the ``+`` next to
``Services`` and add the ``Google Calendar API``.

Then, you can copy the sample ``Code.gs`` file into a new file of the same name
in your script. Update the variables accordingly with the name of your calendar
and the clutter you aim to remove.

Click ``Run`` to test it. If it's successful, you'll likely want to run it on
some interval -- go to ``Triggers`` and add a ``Time-driven`` event on some
interval. That's it!
