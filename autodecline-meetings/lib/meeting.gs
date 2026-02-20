/**
 * Cancel a meeting.
 *
 * @param {string} calendarId The name of the calendar. For a personal calendar, this is probably your email address.
 * @param {string} meetingName The name of the meeting to cancel.
 * @cancelMeeting
 */
function cancelMeeting(calendarId, meetingName) {
  var now = new Date();
  var events = Calendar.Events.list(calendarId, {
    timeMin: now.toISOString(),
    singleEvents: false,
    showDeleted: false,
    q: meetingName,
    maxResults: 20
  });
  if (events.items) {
    for (var i = 0; i < events.items.length; i++) {
      var event = events.items[i];
      if (event.status == "cancelled") {
        continue;
      }

      var start = new Date(event.start.dateTime);
      Logger.log('checking %s (%s)', event.summary, start);

      var updated = false;
      attendees = event.attendees.map((x, i) => {
        if (x.self) {
          updated = x.responseStatus !== 'declined';
          x.responseStatus = 'declined';
        }
        return x;
      });
      if (!updated) {
        Logger.log('skipping: no changes');
        continue;
      }

      Logger.log('declining');
      try {
        event = Calendar.Events.update(
          event,
          calendarId,
          event.id,
          {},
          { 'If-Match': event.etag }
        );
        Logger.log('successfully updated event: %s', event.id);
      } catch (e) {
        Logger.log('update threw an exception: %s', e);
      }
    }
  }
}
