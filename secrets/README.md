# Secrets Directory

Put Docker-only secrets here.

Expected file:

- `gcp-service-account.json` - Google Cloud service account key with access to `BigQuery`.

This directory is mounted into containers as:

- `/run/secrets/gcp-service-account.json`

Do not commit real secret files to Git.
