# Secrets Directory

Put Docker-only secrets here.

Expected file:

- `gcp-service-account.json` - Google Cloud service account key with access to `BigQuery`.

This directory is mounted into containers as:

- `/run/secrets/gcp-service-account.json`

Do not commit real secret files to Git.

## ADC without JSON key

If service account JSON key creation is blocked, you can use Google ADC instead.

What to prepare on the server:

1. Install `gcloud`.
2. Login once on the server:
    ```bash
    gcloud auth application-default login
    ```
3. Copy ADC files into the project directory so Docker can mount them:
    ```bash
    mkdir -p /home/drhtka/projects/anti_fraud_analytics_platform/secrets/gcloud-adc
    cp -R ~/.config/gcloud/* /home/drhtka/projects/anti_fraud_analytics_platform/secrets/gcloud-adc/
    ```
4. In server `.env` set:
    ```bash
    BIGQUERY_PROJECT_ID=your-gcp-project-id
    BIGQUERY_DATASET=anti_fraud_analytics
    BIGQUERY_TABLE=scoring_events
    BIGQUERY_AUTO_CREATE=true
    GOOGLE_APPLICATION_CREDENTIALS=
    GOOGLE_ADC_DIR=./secrets/gcloud-adc
    ```
5. Recreate containers:
    ```bash
    sudo docker compose up -d --force-recreate app worker
    ```

With this setup Docker mounts ADC config into `/root/.config/gcloud`, and the Google client can authenticate without `gcp-service-account.json`.

## If service account key creation is still blocked

If you already set this on the **project**:

- `Policy source` -> `Override parent's policy`
- `Policy enforcement` -> `Replace parent`
- `Rule 1` -> `Not enforced`

but Google Cloud still says **Service account key creation is disabled**, then the block is still coming from a higher level.

What to do:

1. Open **Google Cloud Console**.
2. Switch from the project to the **organization** level resource.
3. Go to **IAM & Admin** -> **Organization Policies**.
4. Find **Disable service account key creation**.
5. Open the policy and click **Manage policy**.
6. Set the policy so key creation is no longer enforced:
    - either `Inherit parent's policy` if parent is already open,
    - or `Override parent's policy` with `Rule 1` -> `Not enforced`.
7. Click **Set policy**.
8. Wait a minute and go back to:
    - **IAM & Admin** -> **Service Accounts** -> your account -> **Keys**.
9. Try **Add key** -> **Create new key** -> **JSON** again.

If it is still blocked after that, then there is another enforced parent policy higher in the hierarchy and it must also be disabled there.

## Server checks after key creation

```bash
ls -la /home/drhtka/projects/anti_fraud_analytics_platform/secrets/gcp-service-account.json
sudo docker compose up -d --force-recreate app worker
```
