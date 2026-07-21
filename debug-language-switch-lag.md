# Debug Session: language-switch-lag

- Status: OPEN
- Symptom: noticeable delay when switching language, especially after scoring has been executed
- Scope: UI language switching and possible post-scoring state/render/network interactions

## Hypotheses

1. Post-scoring state causes expensive full rerender on language switch.
2. Language switch triggers duplicate network requests or scoring recomputation.
3. Extra listeners or timers are attached after scoring and multiply work.
4. Large scoring payload is serialized during locale change.
5. Backend/template response becomes slow only when scored data is present.

## Plan

1. Inspect language switch flow and scoring flow.
2. Identify the narrowest observation points for instrumentation.
3. Add instrumentation only.
4. Reproduce and compare pre-fix evidence.

## Instrumentation Added

1. Client timings in `static/js/language-switch.js` for click, HTML fetch, and pre-replace duration.
2. Server timings in `api/app.py` for `/` rendering, score fetch, localization, explanation, evidence, and asset fingerprinting.
3. Evidence timings in `api/ui_content/evidence.py` with cache-hit vs cache-miss logging.

## Evidence Summary

1. Language switch is implemented as HTML fetch plus full document replacement, not as granular text updates.
2. `ui_translate=1` still executes post-score server work in `index()` when score form data is present.
3. Live browser check on production did not show severe network delay; request time stayed roughly in the 80-130 ms range.
4. After scoring, the translated HTML is much larger, and client-side replace/render cost increases noticeably.

## Current Conclusion

1. Hypothesis 1 is supported: post-scoring state makes language switching heavier because a larger SSR document is re-rendered.
2. Hypothesis 2 is partially supported: translate-only requests avoid event dispatch, but they still go through score/explain/evidence paths.
3. Hypothesis 3 is currently not supported by evidence.
4. Hypothesis 4 is not the main factor based on current evidence.
5. Hypothesis 5 is weakly supported only for cold or uncached server paths; production measurements point more to render cost than backend latency.
