# Your first event

Start with one producer and a short rehearsal before adding microphones or relying
on captions for an audience. Caption Local generates automatic text; a human editor
can improve it, but the combination still needs an event-specific accessibility plan.

## Rehearse the full route

1. Install the service using the [README](../README.md). Download the model before arriving at a venue with limited connectivity.
2. Connect the audio you will actually use. Select an input visible to the browser: a microphone, USB audio interface, or a virtual audio device you have configured separately.
3. Select the spoken language explicitly when known. Automatic detection is less reliable on short phrases. Keep the `small` model for multilingual use.
4. Speak quietly and normally, introduce names and theatre terms, pause, and test background noise. Adjust microphone placement/gain first; try Quiet speech sensitivity if the meter moves but captions do not appear.
5. Check captions on the actual audience display, including text size, contrast, line length, and display delay. Include caption users and accessibility specialists in rehearsal when possible.
6. Run the complete workload for the planned duration. A short successful test does not establish full-event reliability.

System audio and conference audio are not captured automatically. Route them into
an input device that the capture browser can select. Avoid feeding the same mixed
audio to several producers, which produces duplicated captions. Browser microphone
processing is disabled by the app; clean source audio matters.

## Send captions for human review

The capture page and editor are separate roles. A producer can operate capture
while another person reviews text in the caption.ninja editor.

1. Open [caption.ninja/editor](https://caption.ninja/editor) and identify its private automatic-caption/source room. The editor's audience/published room is a different room.
2. In Caption Local, enter that **source room** in the sharing section.
3. Choose whether to send original-language text or English translation. For English output, also choose a mode that produces translation.
4. Enable sharing explicitly. Speak a sentence and confirm that it reaches the editor for review.
5. Use the editor's published caption output for OBS, your projection browser, phones, or an iframe. Check that corrected captions reach that output.
6. Rehearse how much delay the editor needs and whether one editor can keep up with the speakers.

Audio is sent to your inference host. If sharing is enabled, caption text passes
through caption.ninja's relay. Local recognition alone does not make that relay
private or make it available offline. Keep source-room names private. Use a
different source room for each producer whose captions should remain separate.

## During the event

Keep the capture page active and its device awake. Monitor the microphone meter,
buffer size and relay status. Browser suspension, closing the laptop or losing the
audio device can stop capture. A server process remaining healthy does not mean
the microphone is still capturing.

If delay keeps growing, reduce the load: stop unnecessary producers, use
transcription-only where appropriate, or move to a configuration you rehearsed.
The app stops capture when buffered audio exceeds thirty seconds and finishes
what it already captured; it does not continue recording indefinitely.

After a connection failure, automatic retries keep the same audio and request ID.
If retries fail, restore the connection and choose Retry pending audio. Discard
only when you intend to lose that pending audio. See [troubleshooting](TROUBLESHOOTING.md).

## Finish and save

Click Stop and wait for processing to finish. Download the transcript before
closing the page. Neither the browser nor the service automatically archives it.
Then stop the native process with Ctrl+C or use `docker compose down`. Keep the
model cache for the next event.
