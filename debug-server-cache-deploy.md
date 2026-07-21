# Debug Session: server-cache-deploy

- Status: OPEN
- Symptom: local changes are correct, but the production server still serves old behavior after deploy
- Scope: remote deploy state, running containers/processes, reverse proxy or CDN cache, asset invalidation

## Hypotheses

1. Remote repo updated, but running app still uses an old container/process.
2. Server code is new, but Cloudflare or proxy cache serves stale HTML or static assets.
3. Deploy path pulled code without rebuild/restart, so app code or JS bundle did not refresh.
4. Cache headers or asset fingerprinting do not invalidate the changed response path.
5. Domain points to a different runtime instance than the project folder being updated.

## Plan

1. Verify remote git state and recent changes.
2. Verify running containers/processes and their start times.
3. Compare served HTML/asset fingerprints against remote files.
4. Inspect cache-related headers on production responses.
5. If confirmed, apply the minimal deploy/cache fix.

## Evidence Summary

1. Remote repository was already on the expected commit `f39d401`.
2. Production HTML was served as `cf-cache-status: DYNAMIC`, so the main HTML page was not stuck in Cloudflare cache.
3. Production static JS was still old: the served `index.js` did not contain `bootstrapUi()` or `document.body.replaceWith(...)`.
4. The running app and worker containers had been up for around 12 hours, which matched the stale runtime behavior.
5. After `sudo docker compose build --no-cache app worker && sudo docker compose up -d --force-recreate app worker`, the app started serving a new asset fingerprint `bd0376cd6c3954c0` and the new JS code became visible on production.

## Conclusion

1. Hypothesis 1 is confirmed: the git repo on the server was updated, but production was still serving an old container image.
2. Hypothesis 2 is only partially relevant: Cloudflare caches static assets, but this is safe when the asset fingerprint changes.
3. Hypothesis 3 is confirmed: the missing rebuild/recreate step was the direct cause.
4. Hypothesis 4 is worth hardening for future deploys, so HTML responses should use no-store headers.
5. Hypothesis 5 is not supported by current evidence.
