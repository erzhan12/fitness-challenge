You are an expert DevOps + backend engineer working INSIDE my repo (Claude Code / Cursor agent).

Your job:
Take my existing app (Python + FastAPI + Uvicorn + Telegram webhook + OpenAI client + Supabase API) and:

- Deploy it on a **DigitalOcean Droplet** using Docker.
- Use my **Namecheap domain** `habitreward.org` with a subdomain:
  - `fitnesschallenge.habitreward.org`
- Expose a **Telegram webhook** over HTTPS at:
  - `https://fitnesschallenge.habitreward.org/telegram/webhook`
- Set up **CI/CD with GitHub Actions** and a **private container image** using **GitHub Container Registry (GHCR)**.
- Keep all secrets in GitHub Secrets / Droplet env, not in code.

==================================================
1. CURRENT CONTEXT (FACTS YOU MUST ASSUME)
==================================================

Stack & tools:
- Language: Python
- Framework: FastAPI
- Server: Uvicorn
- Libraries: pydantic, python-dotenv
- Bot: Telegram Bot using webhook
- External services:
  - OpenAI API client
  - Supabase API
- Infra:
  - Docker
  - GitHub + GitHub Actions
  - DigitalOcean Droplet (Ubuntu)
- Local config:
  - I use a `.env` file locally.
- Remote config:
  - I use **GitHub Secrets** and environment variables on the server (NOT `.env` committed).

Domain & DNS:
- Registrar: **Namecheap**
- Main domain: `habitreward.org`
  - Already used by ANOTHER Telegram bot via webhook.
- This app MUST use the dedicated subdomain:
  - `fitnesschallenge.habitreward.org`
  - That subdomain must point to the DigitalOcean Droplet and be HTTPS-enabled.
- Do **not** break the existing bot on `habitreward.org`.

Container images:
- I **do not** want a public Docker image.
- Use **GitHub Container Registry (GHCR)** with a **private** image:
  - registry: `ghcr.io`
  - image name pattern: `ghcr.io/<GITHUB_USERNAME>/<REPO_NAME>:latest`

Dockerfile:
- I already have a `Dockerfile`, but currently it **only executes unit tests**, not a production app.
- You need to:
  - Refactor `Dockerfile` to be **multi-stage**:
    - one stage for building & running tests (CI)
    - a final slim stage for running the app in production with Uvicorn.
  - Ensure the production image:
    - does NOT run tests on container startup
    - exposes the correct port (usually `8001`)
    - runs something like:
      - `uvicorn app.main:app --host 0.0.0.0 --port 8001`
      - (adjust module path to match my codebase)

==================================================
2. FIRST, ASK THESE SPECIFIC QUESTIONS
==================================================

Ask me the following in ONE short grouped message and wait:

1. Repo structure:
   - Ask me to paste a short `tree` (or description) showing:
     - where the FastAPI app object lives (e.g. `app/main.py`, `main.py`, etc.)
     - where the Telegram webhook endpoint is defined
     - where my tests live (e.g. `tests/`).

2. Python version:
   - Ask what Python version I am using / targeting (e.g. 3.10, 3.11).

3. Process type:
   - Ask if I need only the main web process, or also background workers (e.g. Celery, RQ, etc.); if I don’t mention any, assume **only web**.

4. DigitalOcean Droplet details:
   - Ask if the Droplet is already created and running Ubuntu (e.g. 22.04).
   - Ask if password SSH or SSH key is used (for GitHub Actions deployment config).

After I reply:
- Summarize the plan in 5–10 bullet points.
- Then proceed step-by-step.

==================================================
3. DOCKERFILE REFACTOR (MULTI-STAGE)
==================================================

Goal:
- Multi-stage Dockerfile that:
  - Stage 1: dev/CI image (install deps, run unit tests).
  - Stage 2: production image (minimal, runs FastAPI app via Uvicorn).

Tasks:
1. Inspect the existing `Dockerfile` and show it to me.
2. Propose a new multi-stage `Dockerfile` that:
   - Uses a recent Python base image (matching my version).
   - Installs dependencies via `pip` (and possibly `poetry`/`pip-tools` if present).
   - Copies only what’s needed into final stage (code + dependencies).
   - Sets:
     - `ENV` or `ENV VARS` placeholders (e.g. `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, etc.)
   - Exposes port `8001`.
   - Uses `CMD` with Uvicorn:
     - `uvicorn <module_path>:app --host 0.0.0.0 --port 8001`.

3. Make sure:
   - `.env` is **not** baked into the image.
   - Environment variables are expected to be passed from Docker / Droplet.

Show me the entire proposed `Dockerfile` and explain briefly what each stage does.

==================================================
4. DIGITALOCEAN DROPLET SETUP (UBUNTU)
==================================================

Assume a fresh Ubuntu Droplet.

Provide **explicit shell commands** for:

1. Basic server setup:
   - Create a non-root user with sudo (if not done).
   - Configure SSH (no root login, etc. – optional but recommended).
   - Install system updates: `apt update && apt upgrade`.

2. Docker installation:
   - Install Docker (official instructions summarized in safe commands).
   - Ensure my user can run `docker` without `sudo` (add to `docker` group).

3. Firewall:
   - Set up `ufw` to:
     - allow SSH (port 22),
     - allow HTTP (80),
     - allow HTTPS (443),
     - then enable firewall.

4. App deployment (first-time manual steps):
   - Install `git`.
   - Clone the repo OR (if using GHCR only) log into GHCR with a PAT and `docker login ghcr.io`.
   - Pull the image: `docker pull ghcr.io/<username>/<repo>:latest`.
   - Run the container:
     - Map internal port `8001` to local port (e.g. `localhost:8001`), NOT directly to 80/443 because we’ll use a reverse proxy.

Explain each step in comments or short text.

==================================================
5. REVERSE PROXY + HTTPS WITH CADDY
==================================================

Use **Caddy** as the reverse proxy on the Droplet (simpler automatic HTTPS).

Tasks:

1. Install Caddy on Ubuntu:
   - Show commands to install from official repository (or a safe recommended method).

2. Caddy config:
   - Create a `Caddyfile` with a server block like:

     - Domain: `fitnesschallenge.habitreward.org`
     - Listen on HTTPS (Caddy should automatically get Let’s Encrypt certs).
     - Reverse proxy to the Docker container on `localhost:8001`.

   - The `Caddyfile` should look roughly like:

     ```
     fitnesschallenge.habitreward.org {
         reverse_proxy localhost:8001
     }
     ```

   - Include anything else required for basic logging and security defaults.

3. Systemd integration:
   - Ensure Caddy runs as a service and starts on boot.

4. Confirm:
   - After DNS is set (next section), Caddy should automatically obtain certificates and serve:
     - `https://fitnesschallenge.habitreward.org`

==================================================
6. NAMECHEAP DNS FOR SUBDOMAIN
==================================================

Provide **exact** instructions to configure DNS in Namecheap:

1. Record to add:
   - Type: `A`
   - Host: `fitnesschallenge`
   - Value: `<DROPLET_PUBLIC_IP>`
   - TTL: use default (e.g. Automatic).

2. Clarify that:
   - The existing setup for `habitreward.org` (main domain) must remain untouched to keep the other bot alive.
   - Only add this new record for the subdomain.

Explain how, after DNS propagates, `fitnesschallenge.habitreward.org` should resolve to the Droplet where Caddy is listening.

==================================================
7. TELEGRAM WEBHOOK SETUP
==================================================

Webhook endpoint & FastAPI:

1. Ensure there is a FastAPI route such as:
   - `POST /telegram/webhook`
   - It should:
     - accept Telegram updates (JSON),
     - quickly return `200 OK`,
     - hand off processing to appropriate logic.

2. Show or create the FastAPI code for this endpoint, with correct type hints & minimal logic (assuming existing bot logic is elsewhere in code).

Webhook registration:

3. Show how to register the webhook with Telegram using my **new bot token** (NOT the existing bot):

   - API call:
     - `https://api.telegram.org/bot<MY_NEW_BOT_TOKEN>/setWebhook`
     - Webhook URL:
       - `https://fitnesschallenge.habitreward.org/telegram/webhook`

4. Provide:
   - a `curl` command version, and
   - a small Python snippet (if needed) to set the webhook.

5. Call out explicitly:
   - Each Telegram bot can only have one webhook.
   - This setup uses the **new** bot token and `fitnesschallenge.habitreward.org`, so it will NOT interfere with the existing bot on `habitreward.org`.

Testing:

6. Give simple steps to test:
   - Check `curl https://fitnesschallenge.habitreward.org/telegram/webhook` returns a sane response (maybe 405 or 200 as expected).
   - Send a message to the new bot and verify logs / behavior in the app.

==================================================
8. ENVIRONMENT VARIABLES & SECRETS
==================================================

Standardize environment management:

1. List environment variables the app needs, for example:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY` or similar
   - Any DB connection strings or other secrets.

2. Local development:
   - Confirm I’ll keep using `.env` locally.
   - Ensure `.env` is in `.gitignore`.
   - Make sure app uses `python-dotenv` ONLY in local/dev context (or in a way that is safe for prod too but doesn’t require `.env` on the server).

3. Production (Droplet + Docker):
   - Show how to run `docker run` with `-e` flags or `--env-file` (but the env file should live **on the server**, not in the repo).
   - Alternatively, show a simple `docker-compose.yml` with `env_file: .env` and explain that `.env` lives ONLY on the server.

4. GitHub Secrets:
   - List the secrets I must add (names and purposes), e.g.:
     - `GHCR_PAT` (GitHub Personal Access Token for GHCR push)
     - `DO_SSH_HOST` (Droplet IP or hostname)
     - `DO_SSH_USER`
     - `DO_SSH_PRIVATE_KEY`
     - `TELEGRAM_BOT_TOKEN` (optional, if used in CI)

==================================================
9. GITHUB ACTIONS CI/CD WITH GHCR (PRIVATE)
==================================================

Set up a GitHub Actions workflow file:

- Path: `.github/workflows/deploy.yml`

Behavior:

- Trigger:
  - On push to `main` (you can assume my default branch is `main`).

Steps:

1. Checkout code.
2. Set up Python and run tests (using the test stage or simple `pytest`).
3. Build Docker image with tag:
   - `ghcr.io/<GITHUB_USERNAME>/<REPO_NAME>:latest`
4. Log in to GHCR using `GHCR_PAT` secret.
5. Push the image to GHCR.
6. SSH into the DigitalOcean Droplet using:
   - `DO_SSH_HOST`, `DO_SSH_USER`, `DO_SSH_PRIVATE_KEY` secrets.
7. On the Droplet:
   - `docker pull` the new image.
   - Restart the container (either:
     - `docker stop` + `docker rm` + new `docker run`, or
     - `docker-compose pull` + `docker-compose up -d` if you define a `docker-compose.yml`).
8. Include comments in the YAML explaining each major block.

Output:

- Provide the full `deploy.yml` content with placeholders for:
  - `<GITHUB_USERNAME>`
  - `<REPO_NAME>`

==================================================
10. DOCUMENTATION (README SECTION)
==================================================

Add or update a section in `README.md` called:

- `## Deployment: DigitalOcean Droplet + Telegram Webhook`

The section should briefly but clearly describe:

1. Required environment variables and how to set them locally (.env) vs on server.
2. How to build and run the Docker image locally for testing.
3. Steps to:
   - provision / prepare the DigitalOcean Droplet,
   - install Docker & Caddy,
   - configure Caddy with `fitnesschallenge.habitreward.org`.
4. Namecheap DNS setup with an `A` record for `fitnesschallenge.habitreward.org`.
5. How to set the Telegram webhook for the new bot.
6. How the GitHub Actions workflow works, and:
   - how to trigger deployment (push to `main`),
   - what secrets must be created.

==================================================
11. INTERACTION STYLE
==================================================

- Work in small steps.
- At each major step:
  - Show me the plan.
  - Show proposed file contents or diffs.
  - Wait for my confirmation before making big or breaking changes.
- Prefer explicit file paths and full config/code snippets over abstract descriptions.
- Assume I’m comfortable running shell commands but appreciate clear, copy-pastable ones.
