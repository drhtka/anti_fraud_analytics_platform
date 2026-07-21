# Debug Session: server-language-switch-stuck

- Status: OPEN
- Symptom: on production the first language switch works, but the next click does not switch language anymore
- Scope: production runtime only, focusing on client rebind after DOM replacement and potential stale module/runtime mismatch

## Hypotheses

1. New language switch buttons are rendered after the first switch, but no click handlers are rebound.
2. `bootstrapUi()` fails after body replacement and leaves the page partially initialized.
3. Production serves mixed JS modules from cache, so the first switch loads inconsistent client code.
4. The client state after the first switch makes the handler exit early on subsequent clicks.
5. Production runtime still differs from local behavior in a way not visible from the repo state alone.

## Plan

1. Reproduce the bug on production in the browser.
2. Inspect production network requests and post-switch DOM state.
3. Inspect current production JS payloads and compare them with expected code paths.
4. Use existing debug endpoints/logs if available to confirm which hypothesis holds.
5. Apply the minimal fix only after evidence confirms the root cause.
