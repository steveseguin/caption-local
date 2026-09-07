# Self-hosted page and guide review

Reviewed on 2026-09-07 using Windows 11 Pro build 26200, Python 3.12.10,
Playwright 1.62.0, Edge 152.0.4191.66 and Node 22.19.0. The baseline was
Caption Local `c090401f80790eb13ec1a276720de75311d15de2` and captionninja
`06bff4c5db1cccebfc0bc43108f8a90aca6653d9`. The commit containing this report
contains the resulting Caption Local changes; the companion editor and browser
bundle are updated directly on captionninja `master`.

## Scope and outcome

The review covers the self-hosted workflow: both Caption Local capture pages,
the private-relay editor and audience overlay, plus all 18 human-facing setup,
deployment, operations and integration guides listed in [guide results](guides.json).
It does not cover every unrelated legacy caption.ninja page.

- **24 UI views:** eight setup/ready/sharing states at 1280×900, 390×900 and
  320×640. Final checks found no page JavaScript errors, failed tested clicks,
  horizontal page overflow or controls outside the viewport horizontally.
- **36 guide renders:** 18 documents at desktop and phone widths, with no broken
  images or horizontal page overflow. Technical reference tables/code blocks
  can scroll within their own containers. Beginner setup choices now use short
  sections and lists instead of wide comparison tables.
- Screenshot inspection covered hierarchy, spacing, wrapping, setup forms,
  guide entry points and primary controls. Keyboard checks cover the capture
  skip link, microphone/language focus after connection, and private setup's
  heading/help/address sequence. This is not a full screen-reader or WCAG audit.
- Caption.ninja's main `index.html` and shared `ws-publisher.js` are unchanged.

## Demonstrated problems and changes

| Finding | Change and observed result |
| --- | --- |
| Optional sharing settings pushed Start far down the capture page. | Capture/save now precedes optional sharing and diagnostics. Ready-state Start moved from 1374 to 746 px on a 1280×900 viewport. Opening sharing previously moved it to 2491 px; it now stays at 746 px. |
| Connection fields occupied space after a successful connection. | The service section folds after success, remains reopenable, and keyboard focus moves to Microphone. Connection errors also appear beside Connect. |
| Capture controls required excessive phone scrolling. | Fields become one column; ready-state Start moved from 1764 to 996 px at width 390. It still requires vertical scrolling on a phone; the keyboard skip link goes directly to capture controls. |
| A rotated editor arrow intercepted a real mobile click on the OBS disclosure. | Decorative arrows no longer capture pointer events and have bounded dimensions. The disclosure click now succeeds. Private workflow cards remain compact and their links wrap. |
| The OBS token form expanded the top navigation card. | It now belongs in the audience room's Room links panel. Private help distinguishes the viewing token from publishing credentials. |
| Private editor setup showed a full, unusable editor beneath the credential form; overlay setup inherited bottom-aligned, non-scrolling overlay styles. | Setup has its own focused, scrollable layout with a named heading and help link. After connection, the audience overlay resumes its caption-only layout. |
| Guides had scattered entry points and narrow beginner tables. | A grouped guide directory links installation, hosting choices, relay setup, troubleshooting, API, security and measurements. Capture pages link to it; every guide under `docs/` links back. Diagrams have text equivalents and full-size links. |

Before/after positions come from [baseline UI results](before.json) and
[final UI results](after.json). They measure layout, not speech latency.

## Representative screenshots

- Capture desktop: [before](capture-before.png), [after](capture-after.png).
- Capture phone: [after](capture-phone.png).
- Editor phone with OBS disclosure: [before](editor-before.png), [after](editor-after.png).
- Viewer setup phone: [before](viewer-before.png), [after](viewer-after.png).
- [Guide directory](guides-desktop.png); [visual introduction](../../docs/SELF-HOSTING.md).

The UI screenshots use synthetic captions and mocked health/relay responses.
They do not demonstrate model readiness, GPU inference or real microphone access.
Documentation uses GitHub's Markdown renderer with a local reading stylesheet,
not screenshots of GitHub's surrounding interface. No caption text was sent to
a public relay. Only public guide Markdown and existing public documentation
images were requested from GitHub.

## Functional regression checks

- Python: **52 passed**, one dependency deprecation warning from Starlette's
  AnyIO `BlockingPortal` alias.
- Caption Local JavaScript: **14 passed**, including retained audio, worklet
  Stop, endpoint/token isolation and bounded publishing.
- Private relay Node tests: **18 passed**, including authorization, queue
  limits, lost acknowledgements, replay, restart gaps and slow consumers.
- [Cross-origin browser capture](connection.json): wrong-token rejection,
  settings round trip, synthetic capture/drain, mock direct-overlay delivery,
  microphone-denial recovery, token privacy and CORS rejection passed.
- [Private-relay browser flow](private-flow.json): actual local Node relay,
  synthetic microphone and fake inference; token setup, editor approval,
  view-only links, room isolation, Stop/drain, restart recovery and terminal
  oversized multilingual payload handling passed. No browser errors or external
  requests. Its review-to-visible sample includes browser automation and is
  not an isolated latency benchmark.
- [Deployed-page browser flow](hosted-flow.json): passed against the actual HTTPS
  GitHub Pages site at captionninja commit `b8c9648`. Capture HTML, stylesheet,
  editor HTML and relay setup script matched the local reviewed bytes. Browser
  loopback permission was granted in the test context; inference and caption
  sockets stayed local. No hosted relay received test captions.

GitHub's [Linux checks](https://github.com/steveseguin/caption-local/actions/runs/34162584242)
and [Windows checks](https://github.com/steveseguin/caption-local/actions/runs/34162584393)
passed on Caption Local `fcb12b5`; the companion
[relay checks](https://github.com/steveseguin/captionninja/actions/runs/34162569247)
and [Pages deployment](https://github.com/steveseguin/captionninja/actions/runs/34162568067)
passed on `b8c9648`.

No new recognition, GPU capacity or sustained-operation claim is made by this
UI review. Physical microphones, assistive technologies, Safari/Firefox and
real phone hardware were not tested here. Existing accuracy and capacity limits
remain in the [deployment profiles](../../docs/DEPLOYMENT-PROFILES.md).

## Reproduce

Install the development dependencies and use a local captionninja checkout at
`samples/captionninja`. From the Caption Local project directory on Windows:

```powershell
.venv\Scripts\python.exe scripts/sync_capture_page.py samples/captionninja --check
.venv\Scripts\python.exe scripts/review_pages.py --output samples/visual-review/ui
.venv\Scripts\python.exe scripts/review_guides.py --output samples/visual-review/guides
.venv\Scripts\python.exe scripts/check_release.py
.venv\Scripts\python.exe -m pytest -q
node --test tests/audio-buffer.test.cjs tests/local-connection.test.cjs tests/relay-config.test.cjs tests/relay-publisher.test.cjs
npm.cmd --prefix samples/captionninja/relay test
$env:CAPTION_TEST_OUTPUT_DIR = 'samples/visual-review'
.venv\Scripts\python.exe scripts/browser_capture_connection.py
.venv\Scripts\python.exe scripts/browser_private_relay.py --output samples/visual-review/private-flow.json
Remove-Item Env:CAPTION_TEST_OUTPUT_DIR
```

Use `.venv/bin/python`, `npm` and the equivalent environment assignment on
Linux. Browser selection is shared with the other test tooling. Guide rendering
requires authenticated `gh` access. Both visual harnesses save full-page and
first-screen PNGs plus JSON; failures in their measured checks return nonzero.
Inspect the screenshots as well: zero overflow alone does not establish usability.
