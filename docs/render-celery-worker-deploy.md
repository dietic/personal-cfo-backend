# Render Celery Worker Deployments

This repository uses a GitHub Actions workflow to deploy the Celery worker service to Render only when relevant code changes. Follow the steps below when (re)creating the Render service or repository secrets.

## 1. Configure the Render Celery Worker Service

1. In the Render dashboard open the Celery worker service.
2. Set **Auto Deploy** to **No** so backend pushes do not redeploy the worker automatically.
3. In the service **Settings** tab, create a **Deploy Hook** and copy the generated URL. The hook will be called by GitHub Actions when the workflow decides a worker redeploy is needed.

## 2. Store the Deploy Hook in GitHub

1. In GitHub navigate to **Settings → Secrets and variables → Actions**.
2. Add a new **Repository secret** named `RENDER_CELERY_DEPLOY_HOOK`.
3. Paste the deploy hook URL from Render as the value and save it.

## 3. How Deploys Are Triggered

- The workflow lives in [`.github/workflows/deploy-celery-worker.yml`](../.github/workflows/deploy-celery-worker.yml).
- On pushes to `main` it triggers **unless** every changed file falls under backend-only paths (for example `app/api/**`, `.github/workflows/**`, `Dockerfile.render`, or `start_app.sh`). Updates to Celery tasks, shared services/models, or dependencies therefore redeploy the worker, while API-only tweaks do not.
- You can also run it manually from the **Actions** tab using the **Run workflow** button and optionally add a note explaining why you triggered it.

## 4. Adjusting Backend-Only Paths

If you introduce new backend-specific directories (or want to exclude additional files such as documentation), update the `paths-ignore` section in the workflow so the worker is redeployed only when necessary.

With this setup the backend web service can keep auto-deploy enabled, while the Celery worker redeploys only when its code or shared logic changes.
