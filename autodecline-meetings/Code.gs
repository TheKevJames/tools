function main() {
  let cal = "me@work.com"

  let clutter = [
    'Office Hours w/ Someone I Do Not Work With',
    'Pet Cam',
    'Wellness Wednesday',
  ];
  clutter.forEach(meeting => AutodeclineMeetings.cancelMeeting(cal, meeting));

  let tooOften = "Daily Standup";
  AutodeclineMeetings.cancelRecurring(cal, tooOften, 3);  // only keep Wednesdays on my calendar
}
