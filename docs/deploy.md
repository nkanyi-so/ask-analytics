# Deploying

**None of the platform steps have been run.** CI builds the image and starts it on every pull request; the steps below are written from Railway's and Vercel's documentation as read on 16 Nov 2026 and still need a first real deploy.

Backend on Railway, from `backend/Dockerfile`. Frontend on Vercel, from `frontend/`.

## Backend (Railway)

1. New service from the GitHub repo. Leave the root directory as the repo root: the image needs `data/` as well as `backend/`.
2. Service variables:

| Variable | Value |
|---|---|
| `RAILWAY_DOCKERFILE_PATH` | `backend/Dockerfile` |
| `ADMIN_TOKEN` | a new random string of at least 32 characters; not the one in your local `.env` |
| `ANTHROPIC_API_KEY` | your key |
| `ANTHROPIC_MODEL` | leave unset for `claude-haiku-5-5` |
| `FRONTEND_ORIGIN` | the Vercel URL, once you have it |
| `ASK_RATE_PER_MINUTE`, `ASK_DAILY_BUDGET_USD` | optional; defaults are 5 and 2 |

3. Settings, Deploy: health check path `/health`.
4. Settings, Networking: generate a public domain. Vercel reaches the backend over the internet, so it must have one; the admin token is what keeps strangers out.

Railway injects `PORT` and the image listens on it. Do not set `EVENT_SOURCE` or `DEPLOYED`.

No Railway config file is committed. Railway's `railway.toml` format stops working for existing services on 1 December 2026 and cannot be used for new ones, so the settings above are made in the dashboard.

### What the image refuses

It sets `DEPLOYED=1`, and with that the app will not start if:

- `ANTHROPIC_API_KEY` is missing. Demo mode answers from recorded fixtures and is for local use only.
- `ADMIN_TOKEN` is missing or shorter than 32 characters.
- `EVENT_SOURCE` is anything but `file`.

The same refusals apply to anything running on Railway, image or not: Railway sets `RAILWAY_ENVIRONMENT_NAME` in every container, and the app treats that as deployed too. So a service that Railway built without this Dockerfile (a misspelt `RAILWAY_DOCKERFILE_PATH`, say) still cannot start in demo mode.

The start-up log names every problem at once. CI builds the image and checks the first refusal and a healthy start on every pull request.

## Frontend (Vercel)

1. New project from the same repo, with Root Directory set to `frontend`.
2. Environment variables: `BACKEND_URL` (the Railway domain, with `https://`) and `ADMIN_TOKEN` (the same value as on Railway). Neither name starts with `NEXT_PUBLIC_`, and neither may.
3. Keep "Automatically expose System Environment Variables" on. The Ask route trusts a visitor's address only when `VERCEL=1`.

Then set `FRONTEND_ORIGIN` on Railway to the Vercel URL and redeploy the backend.

## Check after the first deploy

- The page loads in under two seconds (the Phase 6 gate).
- The Ask box shows no "Demo mode" label.
- Two different networks get separate rate limits. This is the assumption that could not be tested locally: that Vercel sets `x-real-ip` itself, and that `X-Visitor-Address` arrives at Railway unchanged.
- `curl https://<railway-domain>/api/overview?window=7d` returns 401.

## The cache warm

It needs no platform schedule. The backend warms its cache at startup and every five minutes after, inside its own process. If Railway puts the service to sleep when idle, the first request after a sleep pays for a container start, which no cache can help; turn sleeping off for the demo if that matters.
